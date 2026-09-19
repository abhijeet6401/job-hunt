"""
JobHunt Agent — FastAPI backend.

All routes are defined here. Authentication is enforced via a session cookie on every
HTML page load. API routes validate the same cookie.

Env vars required: PASSWORD, GROQ_API_KEY, TAVILY_API_KEY, GOOGLE_SHEETS_ID,
GOOGLE_SERVICE_ACCOUNT_JSON.
"""

# Load .env before any other imports so service modules see env vars at import time.
import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import hashlib
import json
import logging
import re
from typing import Optional, AsyncGenerator, Any, List, Dict, Tuple

from fastapi import Cookie, FastAPI, Form, Request, Response, UploadFile, File
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from services.email_writer import write_emails
    from services.enrich import enrich_job
    from services.form_helper import generate_form_answer
    from services.search import search_jobs, search_social_posts
    from services.sheets import clear_tab, get_job_urls, read_jobs, update_job_status_by_url
    from services.tailor import tailor_resume
except ImportError as e:
    logger.warning(f"Optional AI/Sheets services not fully loaded (missing dependency): {e}")
    write_emails = None
    enrich_job = None
    generate_form_answer = None
    search_jobs = None
    search_social_posts = None
    clear_tab = None
    get_job_urls = None
    read_jobs = None
    update_job_status_by_url = None
    tailor_resume = None

app = FastAPI(title="JobHunt Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.exists("data"):
    app.mount("/data", StaticFiles(directory="data"), name="data")
templates = Jinja2Templates(directory="templates")

SESSION_COOKIE_NAME = "jh_session"
SESSION_DURATION_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _hash_password(password: str) -> str:
    """Return SHA-256 hex digest of the password. Never store plaintext."""
    return hashlib.sha256(password.encode()).hexdigest()


def _get_expected_hash() -> str:
    """Return the hash of the configured PASSWORD env var, defaulting to 'kgp2026' if unset."""
    raw = os.environ.get("PASSWORD", "kgp2026")
    return _hash_password(raw)


def _is_authenticated(session_token: Optional[str]) -> bool:
    """Return True if the session token matches the hashed configured password."""
    if not session_token:
        return False
    try:
        expected = _get_expected_hash()
        return session_token == expected
    except Exception:
        return False


def _require_auth(session_token: Optional[str]) -> bool:
    """Raise a 401 JSONResponse if not authenticated. Use in API routes."""
    return _is_authenticated(session_token)


# ─── Auth routes ─────────────────────────────────────────────────────────────

@app.post("/auth/login")
async def login(password: str = Form(...)):
    """
    Validate the submitted password.

    On success, sets a session cookie containing the hashed password.
    On failure, returns 401 with an error message.
    """
    if _hash_password(password) == _get_expected_hash():
        response = JSONResponse({"ok": True})
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=_get_expected_hash(),
            max_age=SESSION_DURATION_SECONDS,
            httponly=True,
            samesite="lax",
        )
        return response
    return JSONResponse({"ok": False, "error": "Incorrect password"}, status_code=401)


@app.post("/auth/logout")
async def logout():
    """Clear the session cookie."""
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


# ─── Frontend ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, jh_session: Optional[str] = Cookie(default=None)):
    """
    Serve the single-page app.

    Passes `authenticated` to the template so the frontend knows whether to show
    the password screen or the main app immediately.
    """
    return templates.TemplateResponse(
        request,
        "index.html",
        context={"authenticated": bool(_is_authenticated(jh_session))},
    )


# ─── Job Search ──────────────────────────────────────────────────────────────

@app.get("/api/search")
async def api_search(
    role: str = "all",
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Stream job search progress and results via Server-Sent Events.

    Query param: role — "all", "product", "founders_office", "data_analyst", "operations"

    Returns SSE events:
    - type "progress": a status update message string
    - type "result": JSON array of job objects (final event)
    - type "error": error message string
    """
    if not _is_authenticated(jh_session):
        async def _unauthorized():
            yield "data: {\"type\": \"error\", \"message\": \"Unauthorized\"}\n\n"
        return StreamingResponse(_unauthorized(), media_type="text/event-stream")

    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")

    async def _stream() -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(message: str):
            await progress_queue.put(message)

        async def run_search():
            try:
                async def _jobs_progress(msg: str):
                    await progress_queue.put(msg)

                async def _social_progress(msg: str):
                    await progress_queue.put(f"[Social] {msg}")

                # Fetch URLs already in the sheet so we only append new discoveries
                loop = asyncio.get_event_loop()
                try:
                    existing_urls = await loop.run_in_executor(None, get_job_urls)
                except Exception as e:
                    logger.warning(f"Could not fetch existing job URLs: {e}")
                    existing_urls = set()

                jobs_task   = asyncio.create_task(search_jobs(
                    role=role,
                    groq_api_key=groq_api_key,
                    tavily_api_key=tavily_api_key,
                    progress_callback=_jobs_progress,
                    existing_urls=existing_urls,
                ))
                social_task = asyncio.create_task(search_social_posts(
                    role=role,
                    groq_api_key=groq_api_key,
                    tavily_api_key=tavily_api_key,
                    progress_callback=_social_progress,
                    existing_urls=existing_urls,
                ))
                jobs, social_posts = await asyncio.gather(jobs_task, social_task)
                await progress_queue.put(json.dumps({
                    "type": "result",
                    "jobs": jobs,
                    "social_posts": social_posts,
                    "is_refresh": True,
                }))
            except Exception as e:
                logger.error(f"Search error: {e}")
                await progress_queue.put(json.dumps({"type": "error", "message": str(e)}))
            finally:
                await progress_queue.put(None)

        search_task = asyncio.create_task(run_search())

        while True:
            item = await progress_queue.get()
            if item is None:
                break
            try:
                parsed = json.loads(item)
                yield f"data: {json.dumps(parsed)}\n\n"
            except (json.JSONDecodeError, TypeError):
                yield f"data: {json.dumps({'type': 'progress', 'message': item})}\n\n"

        await search_task

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ─── Resume Tailoring ────────────────────────────────────────────────────────

@app.post("/api/tailor")
async def api_tailor(
    jd_text: str = Form(...),
    role_type: str = Form("auto"),
    company_name: str = Form("Unknown Company"),
    role_title: str = Form(""),
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Tailor a resume to a job description and return the PDF + diff.

    Form fields:
    - jd_text: full job description text
    - role_type: "auto", "product", "founders_office", "data_analyst", "operations"
    - company_name: used for the PDF filename and Sheets logging
    - role_title: the actual job title (e.g. "Product Manager") for Sheets logging

    Returns JSON with: diff (list of before/after pairs), role_type, keywords, pdf_filename.
    The PDF download is a separate endpoint /api/tailor/pdf (uses session for auth).
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    groq_api_key = os.environ.get("GROQ_API_KEY", "")

    try:
        result = tailor_resume(
            jd_text=jd_text,
            role_type=role_type,
            company_name=company_name,
            role_title=role_title,
            groq_api_key=groq_api_key,
        )

        # Store PDF bytes and LaTeX source in memory keyed by filename for download endpoints.
        app.state.pending_pdfs = getattr(app.state, "pending_pdfs", {})
        app.state.pending_tex  = getattr(app.state, "pending_tex", {})
        app.state.pending_pdfs[result["pdf_filename"]] = result["pdf_bytes"]
        app.state.pending_tex[result["tex_filename"]]  = result["latex"]

        return JSONResponse({
            "ok": True,
            "diff": result["diff"],
            "role_type": result["role_type"],
            "keywords": result["keywords"],
            "pdf_filename": result["pdf_filename"],
            "tex_filename": result.get("tex_filename", result["pdf_filename"].replace(".pdf", ".tex")),
            "latex": result.get("latex", ""),
        })
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Tailor error: {e}")
        return JSONResponse({"error": f"Unexpected error: {str(e)}"}, status_code=500)


@app.get("/api/tailor/pdf/{filename}")
async def download_pdf(
    filename: str,
    jh_session: Optional[str] = Cookie(default=None),
):
    """Download a previously compiled resume PDF by filename."""
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    pending = getattr(app.state, "pending_pdfs", {})
    pdf_bytes = pending.get(filename)

    if not pdf_bytes:
        # Fallback: re-compile the base template for the role
        try:
            from services.pdf_compiler import compile_latex
            role = "product"
            for r in ["product", "founders_office", "data_analyst", "operations", "finance"]:
                if r in filename.lower():
                    role = r
                    break
            tex_path = f"resumes/{role}.tex"
            if os.path.exists(tex_path):
                with open(tex_path, "r", encoding="utf-8") as f:
                    pdf_bytes = compile_latex(f.read())
        except Exception as e:
            logger.error(f"Fallback PDF compilation failed: {e}")

    if not pdf_bytes:
        return JSONResponse({"error": "PDF could not be generated. Please re-generate the resume."}, status_code=404)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/tailor/tex/{filename}")
async def download_tex(
    filename: str,
    jh_session: Optional[str] = Cookie(default=None),
):
    """Download the raw tailored LaTeX source file."""
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    pending = getattr(app.state, "pending_tex", {})
    tex_content = pending.get(filename)

    if not tex_content:
        role = "product"
        for r in ["product", "founders_office", "data_analyst", "operations", "finance"]:
            if r in filename.lower():
                role = r
                break
        tex_path = f"resumes/{role}.tex"
        if os.path.exists(tex_path):
            with open(tex_path, "r", encoding="utf-8") as f:
                tex_content = f.read()

    if not tex_content:
        return JSONResponse({"error": "LaTeX file not found."}, status_code=404)

    return Response(
        content=tex_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Email Drafting ──────────────────────────────────────────────────────────

@app.post("/api/email")
async def api_email(
    company_name: str = Form(...),
    role: str = Form(...),
    contact_name: str = Form(""),
    company_description: str = Form(...),
    observation: str = Form(""),
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Generate two cold email drafts for a target company and role.

    Form fields:
    - company_name, role, contact_name (optional), company_description, observation (optional)

    Returns JSON with draft_1 and draft_2 strings.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    groq_api_key = os.environ.get("GROQ_API_KEY", "")

    try:
        result = write_emails(
            company_name=company_name,
            role=role,
            contact_name=contact_name,
            company_description=company_description,
            observation=observation,
            groq_api_key=groq_api_key,
        )
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        logger.error(f"Email error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Form Helper ─────────────────────────────────────────────────────────────

@app.post("/api/form")
async def api_form(
    question: str = Form(...),
    role_context: str = Form(""),
    company_name: str = Form(""),
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Generate a specific, metric-backed answer to an application form question.

    Form fields:
    - question: the form question text
    - role_context: optional context about the company/role for better tailoring
    - company_name: optional company name for cleaner Sheets logging

    Returns JSON with answer (string) and word_count (int).
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    groq_api_key = os.environ.get("GROQ_API_KEY", "")

    try:
        result = generate_form_answer(
            question=question,
            role_context=role_context,
            company_name=company_name,
            groq_api_key=groq_api_key,
        )
        return JSONResponse({"ok": True, **result})
    except Exception as e:
        logger.error(f"Form helper error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Saved jobs (Sheets read / clear) ────────────────────────────────────────

@app.get("/api/jobs")
async def api_jobs(jh_session: Optional[str] = Cookie(default=None)):
    """
    Return all jobs and social posts previously saved to the Google Sheets Jobs tab.

    Response JSON:
      { ok, jobs: [...], social_posts: [...], last_updated: "YYYY-MM-DD" | null }

    Used on page load so the user sees their saved history instantly without
    running a new Tavily search.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, read_jobs)
        return JSONResponse({"ok": True, **data})
    except Exception as e:
        logger.error(f"Failed to read jobs from Sheets: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


VALID_DECISION_STATUSES = {"New", "Saved", "Shortlisted", "Applied", "Interviewing", "Offer", "Rejected"}


@app.post("/api/jobs/decision")
async def api_jobs_decision(
    url: str = Form(...),
    status: str = Form(...),
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Record a swipe decision (or pipeline action) for a job.

    Form fields:
    - url:    the job URL (row key in the Jobs tab)
    - status: "Shortlisted" (right swipe), "Rejected" (left swipe), "Applied",
              or "New" (undo)

    Updates the Status column of the matching Jobs-tab row.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if status not in VALID_DECISION_STATUSES:
        return JSONResponse({"error": f"Invalid status: {status}"}, status_code=400)

    loop = asyncio.get_event_loop()
    try:
        found = await loop.run_in_executor(None, update_job_status_by_url, url, status)
        return JSONResponse({"ok": True, "found": found})
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/enrich")
async def api_enrich(
    url: str,
    company: str = "",
    role: str = "",
    jh_session: Optional[str] = Cookie(default=None),
):
    """
    Return deep info for one job card: company snapshot (funding, size, founders,
    news) and a structured digest of the full job description.

    Fetched lazily by the swipe deck for the top few cards. Results are cached
    in memory by URL so each job is only enriched once per server lifetime.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    cache = getattr(app.state, "enrich_cache", None)
    if cache is None:
        cache = app.state.enrich_cache = {}
    if url in cache:
        return JSONResponse({"ok": True, "cached": True, **cache[url]})

    groq_api_key   = os.environ.get("GROQ_API_KEY", "")
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, enrich_job, url, company, role, groq_api_key, tavily_api_key
        )
        cache[url] = result
        return JSONResponse({"ok": True, "cached": False, **result})
    except Exception as e:
        logger.error(f"Enrichment failed for {url}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/jobs/clear")
async def api_jobs_clear(jh_session: Optional[str] = Cookie(default=None)):
    """
    Wipe all data rows from the Jobs tab, keeping the header row intact.

    Used by the 'Clear All' button so the user can start a completely fresh search.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: clear_tab("Jobs"))
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Failed to clear Jobs tab: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── CDC Placements & Senior Outreach Hub ──────────────────────────────────

_placement_cache = {
    "students": None,
    "companies": None,
    "analytics": None,
    "all_candidates": None,
    "notes": None,
}

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")


def _load_placement_json(filename: str, default: Any) -> Any:
    path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
    return default


def get_placed_students_data() -> List[Dict[str, Any]]:
    if _placement_cache["students"] is None:
        _placement_cache["students"] = _load_placement_json("placed_students.json", [])
    return _placement_cache["students"]


def get_companies_summary_data() -> List[Dict[str, Any]]:
    if _placement_cache["companies"] is None:
        _placement_cache["companies"] = _load_placement_json("companies_summary.json", [])
    return _placement_cache["companies"]


def get_placement_analytics_data() -> Dict[str, Any]:
    if _placement_cache["analytics"] is None:
        _placement_cache["analytics"] = _load_placement_json("placement_analytics.json", {})
    return _placement_cache["analytics"]


def get_all_candidates_data() -> List[Dict[str, Any]]:
    if _placement_cache["all_candidates"] is None:
        _placement_cache["all_candidates"] = _load_placement_json("all_candidates.json", [])
    return _placement_cache["all_candidates"]


def get_senior_notes_data() -> Dict[str, Any]:
    if _placement_cache["notes"] is None:
        _placement_cache["notes"] = _load_placement_json("senior_notes.json", {})
    return _placement_cache["notes"]


def save_senior_notes_data(notes: Dict[str, Any]) -> None:
    _placement_cache["notes"] = notes
    path = os.path.join(DATA_FOLDER, "senior_notes.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save senior notes: {e}")


@app.get("/placements", response_class=HTMLResponse)
async def placements_page(request: Request, jh_session: Optional[str] = Cookie(default=None)):
    """Serve the CDC Placements, Senior Directory & Company Explorer Dashboard."""
    return templates.TemplateResponse(
        request,
        "placements.html",
        context={
            "authenticated": bool(_is_authenticated(jh_session)),
            "analytics": get_placement_analytics_data(),
        },
    )


@app.get("/api/placements/analytics")
async def api_placement_analytics():
    """Return top-level placement statistics, CTC brackets, and distributions."""
    return JSONResponse(get_placement_analytics_data())


@app.get("/api/placements/companies")
async def api_placement_companies(
    q: Optional[str] = None,
    season: Optional[str] = None,
    sector: Optional[str] = None,
    dept: Optional[str] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    tier: Optional[str] = None,
    sort: str = "hires",
):
    """
    Return list of placement recruiting companies with statistics and filters.
    Query params: q, season, sector, dept, min_ctc, max_ctc, tier ('hft', 'high', 'mid', 'standard'), sort ('hires', 'ctc', 'name', 'cgpa')
    """
    companies = get_companies_summary_data()
    filtered = companies

    if season and season.lower() != "all":
        sn = season.lower().strip()
        filtered = [c for c in filtered if any(sn in s.lower() for s in c.get("seasons", {}).keys())]

    if q:
        query_norm = q.lower().strip()
        filtered = [
            c for c in filtered
            if query_norm in c["name"].lower()
            or any(query_norm in r.lower() for r in c.get("raw_names", []))
            or any(query_norm in s.lower() for s in c.get("sectors", []))
            or any(query_norm in d.lower() for d in c.get("designations", []))
        ]

    if sector and sector.lower() != "all":
        sec_norm = sector.lower().strip()
        filtered = [c for c in filtered if any(sec_norm in s.lower() for s in c.get("sectors", []))]

    if dept and dept.lower() != "all":
        dept_norm = dept.upper().strip()
        filtered = [c for c in filtered if dept_norm in c.get("departments", {})]

    if min_ctc is not None:
        filtered = [c for c in filtered if c.get("max_ctc_lpa", 0.0) >= min_ctc]

    if max_ctc is not None:
        filtered = [c for c in filtered if c.get("min_ctc_lpa", 0.0) <= max_ctc]

    if tier:
        tier_l = tier.lower()
        if tier_l == "hft":
            filtered = [c for c in filtered if c.get("max_ctc_lpa", 0.0) >= 70.0]
        elif tier_l == "high":
            filtered = [c for c in filtered if 40.0 <= c.get("max_ctc_lpa", 0.0) < 70.0]
        elif tier_l == "mid":
            filtered = [c for c in filtered if 20.0 <= c.get("max_ctc_lpa", 0.0) < 40.0]
        elif tier_l == "standard":
            filtered = [c for c in filtered if c.get("max_ctc_lpa", 0.0) < 20.0]

    if sort == "ctc":
        filtered = sorted(filtered, key=lambda x: x.get("max_ctc_lpa", 0.0), reverse=True)
    elif sort == "name":
        filtered = sorted(filtered, key=lambda x: x.get("name", "").lower())
    elif sort == "cgpa":
        filtered = sorted(filtered, key=lambda x: x.get("avg_cgpa") or 0.0, reverse=True)
    else:  # 'hires'
        filtered = sorted(filtered, key=lambda x: (x.get("total_hires", 0), x.get("max_ctc_lpa", 0.0)), reverse=True)

    return JSONResponse({"ok": True, "total": len(filtered), "companies": filtered})


@app.get("/api/placements/students")
async def api_placement_students(
    q: Optional[str] = None,
    season: Optional[str] = None,
    company: Optional[str] = None,
    dept: Optional[str] = None,
    degree: Optional[str] = None,
    sector: Optional[str] = None,
    placement_type: Optional[str] = None,
    min_cgpa: Optional[float] = None,
    max_cgpa: Optional[float] = None,
    min_ctc: Optional[float] = None,
    max_ctc: Optional[float] = None,
    sort: str = "ctc_desc",
    page: int = 1,
    limit: int = 50,
):
    """
    Return placed seniors with contact options and rich filters.
    """
    students = get_placed_students_data()
    filtered = students

    if season and season.lower() != "all":
        sn = season.lower().strip()
        filtered = [s for s in filtered if sn in s.get("season", "").lower()]

    if q:
        qn = q.lower().strip()
        filtered = [
            s for s in filtered
            if qn in s.get("name", "").lower()
            or qn in s.get("rollno", "").lower()
            or qn in s.get("company", "").lower()
            or qn in s.get("designation", "").lower()
            or qn in s.get("dept", "").lower()
            or qn in s.get("dept_name", "").lower()
            or qn in s.get("email", "").lower()
        ]

    if company and company.lower() != "all":
        cn = company.lower().strip()
        filtered = [s for s in filtered if cn in s.get("company", "").lower() or cn in s.get("placed_in_raw", "").lower()]

    if dept and dept.lower() != "all":
        dn = dept.upper().strip()
        filtered = [s for s in filtered if s.get("dept", "").upper() == dn]

    if degree and degree.lower() != "all":
        deg_norm = degree.upper().strip()
        filtered = [s for s in filtered if deg_norm in s.get("degree", "").upper()]

    if sector and sector.lower() != "all":
        sec_norm = sector.lower().strip()
        filtered = [s for s in filtered if sec_norm in s.get("sector", "").lower()]

    if placement_type and placement_type.lower() != "all":
        pt_norm = placement_type.upper().strip()
        filtered = [s for s in filtered if s.get("placement_type", "").upper() == pt_norm]

    if min_cgpa is not None:
        filtered = [s for s in filtered if s.get("cgpa") is not None and s.get("cgpa") >= min_cgpa]

    if max_cgpa is not None:
        filtered = [s for s in filtered if s.get("cgpa") is not None and s.get("cgpa") <= max_cgpa]

    if min_ctc is not None:
        filtered = [s for s in filtered if s.get("ctc_lpa") is not None and s.get("ctc_lpa") >= min_ctc]

    if max_ctc is not None:
        filtered = [s for s in filtered if s.get("ctc_lpa") is not None and s.get("ctc_lpa") <= max_ctc]

    # Sorting
    if sort == "ctc_desc":
        filtered = sorted(filtered, key=lambda x: x.get("ctc_lpa") or 0.0, reverse=True)
    elif sort == "ctc_asc":
        filtered = sorted(filtered, key=lambda x: x.get("ctc_lpa") or 0.0)
    elif sort == "cgpa_desc":
        filtered = sorted(filtered, key=lambda x: x.get("cgpa") or 0.0, reverse=True)
    elif sort == "name_asc":
        filtered = sorted(filtered, key=lambda x: x.get("name", "").lower())
    elif sort == "company_asc":
        filtered = sorted(filtered, key=lambda x: x.get("company", "").lower())

    total = len(filtered)

    # Attach notes
    notes = get_senior_notes_data()
    for s in filtered:
        rn = s.get("rollno")
        if rn and rn in notes:
            s["notes"] = notes[rn]

    if limit > 0:
        start = (page - 1) * limit
        paginated = filtered[start:start + limit]
    else:
        paginated = filtered

    return JSONResponse({
        "ok": True,
        "total": total,
        "page": page,
        "limit": limit,
        "students": paginated,
    })


@app.get("/api/placements/all-candidates")
async def api_all_candidates(
    q: Optional[str] = None,
    dept: Optional[str] = None,
    is_placed: Optional[bool] = None,
    page: int = 1,
    limit: int = 50,
):
    """Search and browse all 3,173 registered CDC batch candidates."""
    candidates = get_all_candidates_data()
    filtered = candidates

    if q:
        qn = q.lower().strip()
        filtered = [
            c for c in filtered
            if qn in c.get("name", "").lower()
            or qn in c.get("rollno", "").lower()
            or qn in c.get("dept", "").lower()
            or qn in c.get("email", "").lower()
        ]

    if dept and dept.lower() != "all":
        dn = dept.upper().strip()
        filtered = [c for c in filtered if c.get("dept", "").upper() == dn]

    if is_placed is not None:
        filtered = [c for c in filtered if c.get("is_placed") == is_placed]

    total = len(filtered)
    start = (page - 1) * limit
    paginated = filtered[start:start + limit]

    return JSONResponse({
        "ok": True,
        "total": total,
        "page": page,
        "limit": limit,
        "candidates": paginated,
    })


@app.get("/api/placements/matcher")
async def api_placement_matcher(
    cgpa: float,
    dept: str,
    sector: Optional[str] = None,
):
    """
    Evaluate candidate placement readiness and categorize companies into
    Safety (high probability), Target (competitive), and Reach (dream/HFT) tiers.
    """
    companies = get_companies_summary_data()
    dept_upper = dept.upper().strip()
    sec_norm = sector.lower().strip() if sector and sector.lower() != "all" else None

    safety_list = []
    target_list = []
    reach_list = []

    for c in companies:
        c_depts = c.get("departments", {})
        c_sectors = [s.lower() for s in c.get("sectors", [])]

        # Check sector filter
        if sec_norm and not any(sec_norm in s for s in c_sectors):
            continue

        dept_hired_count = c_depts.get(dept_upper, 0)
        total_hires = c.get("total_hires", 0)

        # Has this company hired from candidate's dept, or is it an open hiring company (>= 8 hires across depts)?
        is_dept_eligible = (dept_hired_count > 0) or (total_hires >= 8)

        min_cgpa = c.get("min_cgpa") or 6.5
        avg_cgpa = c.get("avg_cgpa") or 8.0
        max_ctc = c.get("max_ctc_lpa") or 0.0

        comp_summary = {
            "name": c["name"],
            "max_ctc_display": c["max_ctc_display"],
            "max_ctc_lpa": max_ctc,
            "total_hires": total_hires,
            "dept_hires": dept_hired_count,
            "min_cgpa": min_cgpa,
            "avg_cgpa": avg_cgpa,
            "sectors": c.get("sectors", []),
            "roles": c.get("designations", [])[:2],
        }

        if not is_dept_eligible:
            continue

        # Criteria for tiers:
        # Reach: Ultra-high CTC (> 40 LPA) or high CGPA requirement (> cgpa + 0.3)
        if max_ctc >= 45.0 or (avg_cgpa > cgpa + 0.3):
            reach_list.append(comp_summary)
        # Safety: Company hired at or below user's CGPA and min_cgpa <= cgpa - 0.3
        elif min_cgpa <= (cgpa - 0.4) and avg_cgpa <= cgpa:
            safety_list.append(comp_summary)
        # Target: Realistic competitive match
        else:
            target_list.append(comp_summary)

    # Sort each list by max_ctc_lpa desc
    safety_list.sort(key=lambda x: x["max_ctc_lpa"], reverse=True)
    target_list.sort(key=lambda x: x["max_ctc_lpa"], reverse=True)
    reach_list.sort(key=lambda x: x["max_ctc_lpa"], reverse=True)

    return JSONResponse({
        "ok": True,
        "input_cgpa": cgpa,
        "input_dept": dept_upper,
        "safety_count": len(safety_list),
        "target_count": len(target_list),
        "reach_count": len(reach_list),
        "safety": safety_list,
        "target": target_list,
        "reach": reach_list,
    })


@app.get("/api/placements/notes")
async def api_get_notes():
    """Retrieve all senior outreach notes and statuses."""
    return JSONResponse({"ok": True, "notes": get_senior_notes_data()})


@app.post("/api/placements/notes")
async def api_save_note(request: Request):
    """
    Update personal outreach status and note for a senior.
    Payload: {"rollno": "...", "status": "Not Contacted|Contacted|Scheduled|Mentored", "note": "..."}
    """
    try:
        body = await request.json()
        rollno = body.get("rollno")
        if not rollno:
            return JSONResponse({"error": "rollno is required"}, status_code=400)

        notes = get_senior_notes_data()
        notes[rollno] = {
            "status": body.get("status", "Not Contacted"),
            "note": body.get("note", ""),
            "updated_at": body.get("updated_at", ""),
        }
        save_senior_notes_data(notes)
        return JSONResponse({"ok": True, "notes": notes})
    except Exception as e:
        logger.error(f"Error saving note: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/placements/upload")
async def api_upload_placement_csv(
    file: UploadFile = File(...),
    season: str = Form("Custom-Batch"),
):
    """
    Upload and merge an additional placement CSV file directly into the central repository.
    Triggers automated reprocessing and cache refresh.
    """
    try:
        clean_season = re.sub(r"[^a-zA-Z0-9_\-]", "", season.strip()) or "Custom-Batch"
        safe_filename = f"uploaded_{clean_season}_{file.filename}"
        dest_path = os.path.join(DATA_FOLDER, safe_filename)

        contents = await file.read()
        with open(dest_path, "wb") as f:
            f.write(contents)

        from scripts.process_placement_data import process_all_placement_data
        process_all_placement_data()

        # Invalidate in-memory cache
        _placement_cache["students"] = None
        _placement_cache["companies"] = None
        _placement_cache["analytics"] = None
        _placement_cache["all_candidates"] = None

        return JSONResponse({
            "ok": True,
            "message": f"Successfully ingested {file.filename} for season '{season}'",
            "analytics": get_placement_analytics_data(),
        })
    except Exception as e:
        logger.error(f"Error uploading and merging CSV: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Basic health check endpoint for Render."""
    return {"status": "ok"}
