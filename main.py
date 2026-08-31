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
from typing import Optional, AsyncGenerator

from fastapi import Cookie, FastAPI, Form, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.email_writer import write_emails
from services.enrich import enrich_job
from services.form_helper import generate_form_answer
from services.search import search_jobs, search_social_posts
from services.sheets import clear_tab, get_job_urls, read_jobs, update_job_status_by_url
from services.tailor import tailor_resume

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JobHunt Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SESSION_COOKIE_NAME = "jh_session"
SESSION_DURATION_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _hash_password(password: str) -> str:
    """Return SHA-256 hex digest of the password. Never store plaintext."""
    return hashlib.sha256(password.encode()).hexdigest()


def _get_expected_hash() -> str:
    """Return the hash of the configured PASSWORD env var."""
    raw = os.environ.get("PASSWORD", "")
    if not raw:
        raise ValueError("PASSWORD environment variable is not set")
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

        # Store PDF bytes in memory keyed by filename for the download endpoint.
        # In production this is fine for a single-user tool; PDFs are small and ephemeral.
        app.state.pending_pdfs = getattr(app.state, "pending_pdfs", {})
        app.state.pending_pdfs[result["pdf_filename"]] = result["pdf_bytes"]

        return JSONResponse({
            "ok": True,
            "diff": result["diff"],
            "role_type": result["role_type"],
            "keywords": result["keywords"],
            "pdf_filename": result["pdf_filename"],
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
    """
    Download a previously compiled PDF by filename.

    Filenames are returned by /api/tailor and are stored in memory for this request cycle.
    """
    if not _is_authenticated(jh_session):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    pending = getattr(app.state, "pending_pdfs", {})
    pdf_bytes = pending.get(filename)

    if not pdf_bytes:
        return JSONResponse({"error": "PDF not found. Re-generate the resume."}, status_code=404)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
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


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Basic health check endpoint for Render."""
    return {"status": "ok"}
