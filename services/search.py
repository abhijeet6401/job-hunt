"""
Job discovery using Tavily web search + Groq for structured extraction and scoring.

Job board pipeline (two-tier):
  Tier 1 — 5 high-signal queries (Wellfound, LinkedIn jobs, WorkAtAStartup).
    Results extracted, scored, and streamed to the UI immediately via SSE.
  Tier 2 — 4 founder-activity-signal queries (LinkedIn posts, Twitter).
    Results extracted and scored; combined final list sent as the closing SSE event.
  Per-batch Groq is split into two calls:
    Call 1 — structured field extraction (company, role, location, salary …)
    Call 2 — dedicated candidate-fit scoring using a rule-based system prompt.

Social scanner pipeline (search_social_posts):
  1. 22+ queries targeting LinkedIn/Twitter/X posts where founders are hiring.
  2. Groq extracts: poster name/role, company, role hired for, contact method.
  3. Sort by recency tier first (≤3d / ≤7d / ≤14d / older), then match_score.
  4. Save to Google Sheets Jobs tab (Source Type = "Social Post").
"""

import asyncio
import json
import logging
from datetime import date

from groq import Groq
from tavily import TavilyClient

from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Candidate profile (used in social-post extraction) ────────────────────────
CANDIDATE_PROFILE = """
Candidate profile (use this to score each job's fit):
- Economics undergraduate at IIT Kharagpur (Class of 2027), CGPA 8.03/10, Minor in Mathematics & Computing, Micro-Spl in AI.
- UN Millennium Fellow (selected among 5,000 students globally for UN SDG leadership).
- Snabbit (PM & Strategy Intern): Scaled retention GOV 20% to 50% with Blush Prive, saved Rs 50L/mo in vendor negotiations, managed 100+ SKUs.
- Aequitas Investments (AI Product & Finance Intern, $1Bn AUM): Built PERN + TypeScript research deduplication platform & custom CRM.
- 3one4 Capital (Portfolio Strategy Intern): Formulated venture debt & financing playbooks, supported 3 consumer/fintech startups on unit economics.
- Felix Advisory & India Accelerator: VC due diligence, evaluated early-stage startups on TAM/SAM/SOM, benchmarked $130B market.
- Frost & Sullivan (Analytics Intern): Predictive time-series modeling on $23M+ sales data in Power BI with DAX & SQL.
- JobHunt Agent (AI Automation Self-Project): Full-stack FastAPI AI assistant aggregating 100+ listings via Tavily API and xAI LLM.
- Competitions: Winner Product Management General Championship IIT KGP, Bronze FRAMMER AI Data Analytics GC, Runners-up ICC Bikaji M&A case.
- CDC Departmental Representative at IIT Kharagpur (placement operations for 6000+ students).
- Skills: Product Management, Data Analytics, Python, SQL, Power BI, DAX, React, TypeScript, Financial Modeling, DCF, Econometrics.
- Targeting: Product Manager, APM, Founder's Office, Chief of Staff, Venture Capital / Strategy, Data Analyst, Operations roles.
- Company stage preference: early-stage to growth-stage startups and high-growth tech firms.
- Open to: Remote, Bangalore, Mumbai, Gurgaon, and Delhi NCR roles.
- NOT a fit for: senior roles requiring >5 years experience.
"""

# ── Dedicated scoring system prompt (used as system message for scoring call) ─
SCORING_SYSTEM_PROMPT = """You are evaluating job fit for a specific candidate. Be ruthless and specific.

Candidate: Abhijeet Kumar, B.S. (Hons.) in Economics at IIT Kharagpur (Class of 2027, CGPA 8.03/10, Minor in Maths & Computing, Micro-Spl in AI).
Background: Product & Strategy at Snabbit, AI Product Management & Finance at Aequitas ($1Bn AUM fund), Portfolio Management & Strategy at 3one4 Capital, Research at Felix Advisory, Investment Analyst at India Accelerator, Growth Analytics at Frost & Sullivan. Winner PM General Championship IIT Kharagpur, Bronze FRAMMER AI Data Analytics GC, Runners up Indian Case Challenge (Bikaji M&A). CDC Departmental Representative. UN Millennium Fellow, NTSE Scholar, KVPY SA AIR 1487.
Hard skills: Python, SQL, Power BI, DAX, React, TypeScript, Node.js, Pandas, Scikit-learn, Financial Modeling, DCF, Econometrics, VECM, time-series forecasting, PRD writing, REST APIs.
Soft strengths: High agency, cross-functional execution across product, strategy, data, and finance; leadership at CDC; strong analytical and mathematical pedigree from IIT Kharagpur.
Targeting: APM, Product Manager, Founder's Office, Chief of Staff, Venture Capital, Strategy, Biz Ops, Data Analyst, Business Analyst, Operations roles at high-growth startups and tech companies. Open to remote, Bangalore, Mumbai, Gurgaon.

Apply these rules to score each job 0-100 on match likelihood:
- Subtract 30 points if it requires 3+ years of experience explicitly stated
- Subtract 20 points if it is at a company with 500+ employees
- Add 20 points if it mentions product management, data analytics, SQL/Python, venture capital, or financial modeling
- Add 15 points if it is at a seed to Series B company
- Add 10 points if it is remote or based in Bangalore/Mumbai/Gurgaon
- Add 15 points if it explicitly welcomes strong analytical, product, or generalist backgrounds
- Add 10 points if it mentions 0-2 years experience, freshers, or new grads"""

# ── Tiered search queries ─────────────────────────────────────────────────────
# Role filter → search keyword fragment used to template per-source queries.
ROLE_KEYWORDS = {
    "product":         '"product manager" OR "APM" OR "associate product manager"',
    "founders_office": '"founder\'s office" OR "chief of staff" OR "founders office" OR generalist OR "venture capital"',
    "data_analyst":    '"data analyst" OR "business analyst" OR "product analyst" OR "data scientist"',
    "operations":      '"operations" OR "biz ops" OR "business operations" OR "growth ops"',
    "finance":         '"investment analyst" OR "venture capital" OR "equity research" OR "financial analyst"',
    "all":             'product OR "APM" OR "founder office" OR "chief of staff" OR "data analyst" OR "investment analyst" OR "biz ops"',
}

# Tier 1: one high-signal query per job source, templated with the role keywords.
# Covers global startup boards + India-focused boards (Cutshort, Instahyre, Peerlist, Hirect).
TIER1_QUERY_TEMPLATES = [
    "site:workatastartup.com {kw}",
    "site:wellfound.com/jobs {kw} startup 2026",
    "site:linkedin.com/jobs {kw} startup India remote 2026",
    'site:linkedin.com/jobs "0-2 years" OR "fresher" OR "new grad" {kw} 2026',
    "site:cutshort.io {kw} startup 2026",
    "site:instahyre.com {kw} startup Bangalore OR remote",
    "site:ycombinator.com/companies {kw} jobs India OR remote",
    "site:peerlist.io/jobs {kw} startup 2026",
    "site:hirect.in {kw} startup",
]

# Tier 2: founder-activity signals — static fallback when LLM query generation fails
TIER2_FALLBACK_QUERIES = [
    'site:linkedin.com/posts "just closed" OR "seed round" startup hiring product 2026',
    'site:linkedin.com/posts "we are a team of" startup "looking for" product 2026',
    'site:twitter.com "hiring" "product" startup seed India remote 2026',
    'site:twitter.com "join us" startup "product manager" OR "generalist" 2026',
]


def _tier1_queries(role: str) -> list[str]:
    """Build the per-source tier-1 query list for the selected role filter."""
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    return [t.format(kw=kw) for t in TIER1_QUERY_TEMPLATES]


def _generate_tier2_queries(groq_client: Groq, role: str) -> list[str]:
    """
    Ask Groq for fresh founder-activity-signal queries so each refresh explores
    different phrasing instead of replaying the same fixed list. Falls back to
    TIER2_FALLBACK_QUERIES on any failure.
    """
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    prompt = f"""Generate 5 web search queries to find startup hiring signals posted in the
last week (today is {date.today().isoformat()}). Target: posts by founders on LinkedIn
(site:linkedin.com/posts) and Twitter/X (site:twitter.com or site:x.com) announcing that
their seed-to-Series-B startup is hiring for roles matching: {kw}.
Prefer India or remote. Vary the hiring phrasing across queries (e.g. "we're hiring",
"looking for our first", "join us as", "just raised ... hiring", "DM me if").
Each query must include a site: filter and the year 2026.
Return ONLY a JSON array of 5 query strings."""
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.9,
        )
        raw   = response.choices[0].message.content.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return TIER2_FALLBACK_QUERIES
        queries = [str(q) for q in json.loads(raw[start:end]) if isinstance(q, str) and q.strip()]
        return queries[:6] or TIER2_FALLBACK_QUERIES
    except Exception as e:
        logger.warning(f"LLM query generation failed, using fallback queries: {e}")
        return TIER2_FALLBACK_QUERIES

SOCIAL_SEARCH_QUERIES = [
    # ── LinkedIn posts ────────────────────────────────────────────────────────
    'site:linkedin.com/posts hiring "product manager" OR "APM" OR "founder office" OR "data analyst" OR "operations" startup 2026',
    'site:linkedin.com/posts "we are hiring" startup "product" India OR remote 2026',
    'site:linkedin.com/posts "looking for" "product manager" OR "APM" startup seed OR "series a" 2026',
    'site:linkedin.com/posts "join our team" AI startup product India 2026',
    'site:linkedin.com/posts hiring "0-2 years" OR "fresher" OR "no experience required" startup product 2026',
    'site:linkedin.com/posts "DM me" OR "reach out" hiring product startup India 2026',
    'site:linkedin.com/posts founder hiring generalist OR "chief of staff" startup India 2026',
    'site:linkedin.com/posts "open position" product startup seed "series" India 2026',
    'site:linkedin.com/posts "early career" OR "new grad" startup product manager India 2026',
    'site:linkedin.com/posts "biz ops" OR "growth" OR "strategy" startup hiring India 2026',
    'site:linkedin.com/posts "building our team" AI startup India 2026',
    # ── X / Twitter posts ─────────────────────────────────────────────────────
    'site:twitter.com "we are hiring" startup product manager remote 2026',
    'site:twitter.com hiring "APM" OR "associate product manager" startup 2026',
    'site:twitter.com "looking for" "founder office" OR generalist startup India 2026',
    'site:twitter.com YC hiring product AI startup 2026',
    'site:twitter.com "DM me" hiring product startup India remote 2026',
    'site:twitter.com founder hiring "0 to 1" OR "zero to one" product startup India 2026',
    'site:twitter.com "join us" startup product AI India remote 2026',
    'site:x.com hiring startup "product manager" OR "APM" India 2026',
    'site:x.com "we are building" startup hiring product generalist India 2026',
    'site:x.com "open to applications" OR "apply now" founder startup product 2026',
    # ── General founder / direct posts ────────────────────────────────────────
    '"we are hiring" startup product AI India 2026 -site:linkedin.com -site:twitter.com -site:x.com',
    '"join our team" AI product startup India remote 2026 -job -careers',
    '"building our team" startup product AI India 2026',
    '"early stage" startup hiring product OR generalist India 2026 founder',
    '"growth hacker" OR "biz ops" startup hiring India 2026 seed series',
    '"campus hire" OR "new grad" startup product manager India 2026',
]

_FRESHNESS_SUFFIX = " after:2026-05-01"


def _run_tavily_query(
    client: TavilyClient,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[dict]:
    """
    Run a single Tavily search restricted to the past 7 days.

    Uses days=7 if the client accepts it (tavily-python ≥0.3); otherwise appends
    an after: date qualifier to the query string as a fallback.
    search_depth="advanced" returns richer page content (used for tier-1 sources
    so the open/closed check sees real page text, not just a snippet).
    """
    try:
        try:
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                days=7,
            )
        except TypeError:
            # older tavily-python client — fall back to date qualifier in query
            response = client.search(
                query=query + _FRESHNESS_SUFFIX,
                max_results=max_results,
                search_depth=search_depth,
            )
        return response.get("results", [])
    except Exception as e:
        logger.warning(f"Tavily query failed for '{query}': {e}")
        return []


def _url_deduplicate(results: list[dict]) -> list[dict]:
    """Remove duplicate raw results by URL, keeping first occurrence."""
    seen = set()
    out  = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            out.append(r)
    return out


def _company_deduplicate(jobs: list[dict]) -> list[dict]:
    """
    For each company name, keep only the job with the highest match_score.

    Normalises company name to lowercase+stripped for comparison so minor
    variations ("Razorpay" vs "razorpay Inc") collapse into one entry.
    """
    best: dict[str, dict] = {}
    for job in jobs:
        key   = job.get("company", "unknown").lower().strip()
        score = job.get("match_score", 0)
        if key not in best or score > best[key].get("match_score", 0):
            best[key] = job
    return list(best.values())


def _extract_job_fields_only(groq_client: Groq, raw_results: list[dict]) -> list[dict]:
    """
    Call 1 of 2: extract structured fields from a batch of raw Tavily results.
    Does NOT score — scoring is a separate dedicated call.
    """
    if not raw_results:
        return []

    batch_text = "\n\n---\n\n".join([
        f"URL: {r.get('url', '')}\nTitle: {r.get('title', '')}\nSnippet: {r.get('content', '')}"
        for r in raw_results
    ])

    prompt = f"""You are extracting structured job listing data.

For each search result below, output a JSON array. Each element must have these exact keys:
- company:     string  (company name, or "Unknown")
- role:        string  (job title as listed)
- salary:      string  (e.g. "8-12 LPA" or "Not mentioned")
- location:    string  (e.g. "Remote", "Bangalore", "Hybrid - Mumbai")
- source:      string  (LinkedIn / Wellfound / WorkAtAStartup / Naukri / Twitter / Web)
- summary:     string  (one sentence: what the company does and its stage)
- url:         string  (URL from the result)
- is_job:      boolean (true only if this is a real, open job posting — not a blog, news,
                        category/listing index page, or aggregator landing page)
- is_open:     boolean (false if the page content says "filled", "closed", "expired",
                        "no longer accepting", "position has been filled", or shows a
                        past application deadline)
- date_posted: string  (posting date if visible, e.g. "2026-06-05"; otherwise "Unknown")

Only include entries where is_job is true. Return only a valid JSON array. No other text.

Search results:
{batch_text}"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        jobs = json.loads(raw[start:end])
        out  = []
        for j in jobs:
            if not j.get("is_job", False):
                continue
            if not j.get("is_open", True):
                logger.info(f"Filtered closed job: {j.get('company')} — {j.get('role')}")
                continue
            j["date_posted"] = j.get("date_posted", "Unknown") or "Unknown"
            out.append(j)
        return out
    except Exception as e:
        logger.error(f"Groq extraction (call 1) failed: {e}")
        return []


def _score_jobs_batch(groq_client: Groq, jobs: list[dict]) -> list[dict]:
    """
    Call 2 of 2: score a batch of extracted jobs using a rule-based system prompt.
    Returns a list of {score, reason} dicts — one per job, same order.
    Falls back to score=50 / reason="" on any parse failure.
    """
    if not jobs:
        return []

    jobs_text = "\n\n---\n\n".join([
        f"Job {i + 1}: {j.get('company', 'Unknown')} — {j.get('role', 'Unknown')}\n"
        f"Location: {j.get('location', 'Unknown')}\n"
        f"Summary: {j.get('summary', '')}\n"
        f"URL: {j.get('url', '')}"
        for i, j in enumerate(jobs)
    ])

    user_msg = (
        f"Score each of these {len(jobs)} job listings.\n\n"
        f"{jobs_text}\n\n"
        f"Return a JSON array with exactly {len(jobs)} objects in the same order, "
        f"each with: score (integer 0-100) and reason "
        f"(one sentence explaining the top factor that drove the score up or down)."
    )

    fallback = [{"score": 50, "reason": ""} for _ in jobs]

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=1500,
            temperature=0,
        )
        raw   = response.choices[0].message.content.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return fallback
        scores = json.loads(raw[start:end])
        result = []
        for s in scores[: len(jobs)]:
            result.append({
                "score":  max(0, min(100, int(float(s.get("score", 50))))),
                "reason": s.get("reason", ""),
            })
        while len(result) < len(jobs):
            result.append({"score": 50, "reason": ""})
        return result
    except Exception as e:
        logger.error(f"Groq scoring (call 2) failed: {e}")
        return fallback


def _extract_job_fields(groq_client: Groq, raw_results: list[dict]) -> list[dict]:
    """
    Full extraction pipeline for one batch: structured fields (call 1) then
    dedicated candidate-fit scoring (call 2). Merges results before returning.
    """
    jobs = _extract_job_fields_only(groq_client, raw_results)
    if not jobs:
        return []
    scores = _score_jobs_batch(groq_client, jobs)
    for job, s in zip(jobs, scores):
        job["match_score"]  = max(1, min(100, s["score"]))
        job["score_reason"] = s["reason"]
    return jobs


def _recency_tier(date_str: str) -> int:
    """
    Return a recency bucket for sorting.  Lower = more recent.
      0 → ≤ 3 days old
      1 → ≤ 7 days
      2 → ≤ 14 days
      3 → older / unknown
    """
    if not date_str or date_str == "Unknown":
        return 2
    try:
        from datetime import date as _date
        diff = (_date.today() - _date.fromisoformat(date_str)).days
        if diff <= 3: return 0
        if diff <= 7: return 1
        if diff <= 14: return 2
        return 3
    except (ValueError, TypeError):
        return 2


def _extract_social_fields(groq_client: Groq, raw_results: list[dict]) -> list[dict]:
    """
    Extract structured social-post hiring data from a batch of Tavily results.

    Returns entries where a founder/hiring manager is directly posting about an open role,
    with candidate match scoring identical to the job board pipeline.
    """
    if not raw_results:
        return []

    batch_text = "\n\n---\n\n".join([
        f"URL: {r.get('url', '')}\nTitle: {r.get('title', '')}\nSnippet: {r.get('content', '')}"
        for r in raw_results
    ])

    prompt = f"""
{CANDIDATE_PROFILE}

You are extracting structured data from social media posts (LinkedIn, Twitter/X) where
founders, co-founders, CTOs, or hiring managers are DIRECTLY posting about open roles.

For each search result below, output a JSON array. Each element must have these exact keys:
- poster_name:    string  (name of the person who posted, or "Unknown")
- poster_role:    string  (their role: "Co-Founder", "CTO", "Founder", "HR Manager", "Unknown")
- company:        string  (company name, or "Unknown")
- role_hiring:    string  (role they are hiring for, e.g. "Product Manager", "APM", "Generalist")
- contact_method: string  (how to apply: "DM on LinkedIn", "Email: x@y.com", "Link in bio", "Unknown")
- is_founder_post: boolean (true if poster is founder/co-founder/CTO — NOT an HR recruiter)
- post_date:      string  (post date if visible, e.g. "2026-06-05"; otherwise "Unknown")
- url:            string  (URL from the result)
- post_snippet:   string  (1-2 sentences summarising what the post says about the role/company)
- source:         string  ("LinkedIn" / "Twitter" / "X" / "Web")
- match_score:    integer (1-100, candidate fit score)
- score_reason:   string  (short phrase, e.g. "Seed AI startup, founder post, 0-2yr exp, India")
- is_hiring_post: boolean (true ONLY if this is a genuine hiring post from a founder/hiring manager —
                           NOT a job board listing, news article, blog post, or recruitment agency ad)

Scoring guidance:
- 80-100: Seed–Series B startup, role is PM/APM/Founder's Office/Ops/Data, direct founder post, India or remote
- 60-79:  Good match but one gap (HR poster not founder, 2-4yr exp, location mismatch)
- 40-59:  Right function but senior level or mid-sized company
- <40:    Enterprise, senior-only, unrelated function, or not a genuine hiring post

Only include entries where is_hiring_post is true. Return only a valid JSON array. No other text.

Search results:
{batch_text}
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        posts = json.loads(raw[start:end])
        out   = []
        for p in posts:
            if not p.get("is_hiring_post", False):
                continue
            p["match_score"]  = max(1, min(100, int(p.get("match_score", 50))))
            p["score_reason"] = p.get("score_reason", "")
            p["post_date"]    = p.get("post_date", "Unknown") or "Unknown"
            out.append(p)
        return out
    except Exception as e:
        logger.error(f"Groq social extraction failed: {e}")
        return []


def _find_recruiter_email(tavily_client: TavilyClient, groq_client: Groq, company: str) -> str:
    """
    Try to find a recruiter, founder, or careers email for a given company.

    Runs a targeted Tavily search, then uses Groq to extract any email address.
    Returns the email string, or empty string if not found.
    """
    if not company or company.lower() in ("unknown", ""):
        return ""

    query = f'{company} founder email OR hiring manager email OR careers@ OR jobs@'
    try:
        results  = tavily_client.search(query=query, max_results=3, search_depth="basic")
        snippets = " ".join(
            r.get("content", "") + " " + r.get("title", "")
            for r in results.get("results", [])
        )
    except Exception as e:
        logger.warning(f"Recruiter email search failed for '{company}': {e}")
        return ""

    if not snippets.strip():
        return ""

    prompt = f"""
Extract one recruiter, founder, or hiring-related email address from the text below.
Return only the email address as a plain string. If no email is present, return null.

Company: {company}
Text: {snippets[:1500]}
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0,
        )
        result = response.choices[0].message.content.strip().lower()
        if result == "null" or "@" not in result:
            return ""
        for token in result.split():
            if "@" in token:
                return token.strip(".,;\"'<>")
        return ""
    except Exception as e:
        logger.warning(f"Groq email extraction failed for '{company}': {e}")
        return ""


async def search_jobs(
    role: str,
    groq_api_key: str,
    tavily_api_key: str,
    progress_callback=None,
    existing_urls: set = None,
) -> list[dict]:
    """
    Two-tier job discovery pipeline.

    Tier 1 (5 high-signal queries) → extract+score → emit tier1_result SSE immediately.
    Tier 2 (4 founder-signal queries) → extract+score new URLs only.
    Combined → company dedup → email lookup → Sheets save → return all new jobs.

    existing_urls: URLs already in the Jobs sheet (skip on refresh).
    progress_callback: async callable(str) for SSE progress updates.
    """
    groq_client   = Groq(api_key=groq_api_key)
    tavily_client = TavilyClient(api_key=tavily_api_key)
    loop          = asyncio.get_event_loop()
    known         = existing_urls or set()
    batch_size    = 10

    # ── Tier 1: high-signal job-board queries ────────────────────────────────
    tier1_queries = _tier1_queries(role)
    if progress_callback:
        await progress_callback(
            f"Running {len(tier1_queries)} high-signal searches "
            f"(Wellfound, LinkedIn, WorkAtAStartup, Cutshort, Instahyre, YC, Peerlist)..."
        )

    tier1_raw_nested = await asyncio.gather(*[
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q, 5, "advanced")
        for q in tier1_queries
    ])
    tier1_raw    = [r for batch in tier1_raw_nested for r in batch]
    tier1_unique = _url_deduplicate(tier1_raw)

    if progress_callback:
        await progress_callback(
            f"{len(tier1_unique)} unique tier-1 results. Extracting fields and scoring..."
        )

    tier1_jobs: list[dict] = []
    for i in range(0, len(tier1_unique), batch_size):
        batch = tier1_unique[i : i + batch_size]
        jobs  = await loop.run_in_executor(None, _extract_job_fields, groq_client, batch)
        tier1_jobs.extend(jobs)
        if progress_callback:
            await progress_callback(f"Scored {len(tier1_jobs)} tier-1 jobs so far...")

    tier1_jobs = _company_deduplicate(tier1_jobs)
    tier1_jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)
    tier1_urls = {j.get("url", "") for j in tier1_jobs}

    # Stream tier-1 results immediately so the user sees high-signal cards first
    tier1_new = [j for j in tier1_jobs if j.get("url", "") not in known]
    if progress_callback and tier1_new:
        await progress_callback(json.dumps({
            "type": "tier1_result",
            "jobs": tier1_new,
        }))
        await progress_callback(
            f"Showing {len(tier1_new)} high-signal results. "
            f"Scanning founder posts for more..."
        )

    # ── Tier 2: founder-activity signal queries (LLM-generated, fresh per run) ─
    tier2_queries = await loop.run_in_executor(
        None, _generate_tier2_queries, groq_client, role
    )
    if progress_callback:
        await progress_callback(
            f"Running {len(tier2_queries)} founder-activity signal searches..."
        )

    tier2_raw_nested = await asyncio.gather(*[
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q)
        for q in tier2_queries
    ])
    tier2_raw = [r for batch in tier2_raw_nested for r in batch]
    # Remove URLs already seen in tier 1
    tier2_raw    = [r for r in tier2_raw if r.get("url", "") not in tier1_urls]
    tier2_unique = _url_deduplicate(tier2_raw)

    if progress_callback:
        await progress_callback(
            f"{len(tier2_unique)} new tier-2 results. Extracting and scoring..."
        )

    tier2_jobs: list[dict] = []
    for i in range(0, len(tier2_unique), batch_size):
        batch = tier2_unique[i : i + batch_size]
        jobs  = await loop.run_in_executor(None, _extract_job_fields, groq_client, batch)
        tier2_jobs.extend(jobs)

    # ── Combine, dedup, sort ─────────────────────────────────────────────────
    all_jobs = _company_deduplicate(tier1_jobs + tier2_jobs)
    all_jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)

    if progress_callback:
        await progress_callback(f"Finding recruiter emails for {len(all_jobs)} companies...")

    # Semaphore caps concurrent Groq calls during the parallel email lookup phase
    groq_sem = asyncio.Semaphore(3)

    async def _bounded_email_lookup(company: str) -> str:
        async with groq_sem:
            return await loop.run_in_executor(
                None, _find_recruiter_email, tavily_client, groq_client, company
            )

    email_results = await asyncio.gather(*[
        _bounded_email_lookup(job.get("company", ""))
        for job in all_jobs
    ])
    for job, email in zip(all_jobs, email_results):
        job["recruiter_email"] = email

    # Filter to genuinely new jobs (not already in Sheets)
    new_jobs = [j for j in all_jobs if j.get("url", "") not in known]

    if progress_callback:
        skipped = len(all_jobs) - len(new_jobs)
        msg = f"Found {len(new_jobs)} new jobs"
        if skipped:
            msg += f" ({skipped} already saved, skipped)"
        await progress_callback(msg + ". Saving to Google Sheets...")

    today = str(date.today())
    for job in new_jobs:
        try:
            append_row("Jobs", [
                today,
                job.get("date_posted", "Unknown"),
                job.get("company", ""),
                job.get("role", ""),
                job.get("salary", "Not mentioned"),
                job.get("location", ""),
                job.get("source", ""),
                job.get("url", ""),
                job.get("recruiter_email", ""),
                job.get("summary", ""),
                role,
                "New",
                "Job Board",
                job.get("match_score", 50),
            ])
        except Exception as e:
            logger.warning(f"Failed to save job to Sheets: {e}")

    if progress_callback:
        top = new_jobs[0] if new_jobs else {}
        await progress_callback(
            f"Done. {len(new_jobs)} new jobs found and saved. "
            + (f"Top match: {top.get('company', '')} ({top.get('match_score', 0)}/100)." if top else "")
        )

    return new_jobs


async def search_social_posts(
    role: str,
    groq_api_key: str,
    tavily_api_key: str,
    progress_callback=None,
    existing_urls: set = None,
) -> list[dict]:
    """
    Social Job Scanner: discover roles posted directly by founders on LinkedIn/X.

    1.  26 parallel Tavily queries targeting LinkedIn/Twitter/X hiring posts.
    2.  URL-level deduplication.
    3.  Groq extraction — extracts poster name/role, company, role hired for,
        contact method, and match score (batches of 10).
    4.  Sort by recency tier first (≤3d / ≤7d / ≤14d / older), then match_score.
    5.  Save to Google Sheets — skips URLs already in existing_urls.
    6.  Return only posts whose URLs are NOT in existing_urls (new discoveries only).

    existing_urls: set of URLs already in the Jobs sheet; used to deduplicate on refresh.
    progress_callback: optional async callable(message: str) for SSE updates.
    """
    groq_client   = Groq(api_key=groq_api_key)
    tavily_client = TavilyClient(api_key=tavily_api_key)
    loop          = asyncio.get_event_loop()

    if progress_callback:
        await progress_callback(
            f"Scanning {len(SOCIAL_SEARCH_QUERIES)} social queries for founder hiring posts..."
        )

    raw_nested = await asyncio.gather(*[
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q)
        for q in SOCIAL_SEARCH_QUERIES
    ])

    all_raw = [r for batch in raw_nested for r in batch]

    if progress_callback:
        await progress_callback(f"Got {len(all_raw)} social results. Deduplicating by URL...")

    unique_raw = _url_deduplicate(all_raw)

    if progress_callback:
        await progress_callback(
            f"{len(unique_raw)} unique social results. Extracting with AI..."
        )

    batch_size = 10
    all_posts  = []
    for i in range(0, len(unique_raw), batch_size):
        batch = unique_raw[i : i + batch_size]
        posts = await loop.run_in_executor(None, _extract_social_fields, groq_client, batch)
        all_posts.extend(posts)

    # Sort by recency tier (ascending) then match_score (descending)
    all_posts.sort(
        key=lambda p: (_recency_tier(p.get("post_date", "Unknown")), -p.get("match_score", 0))
    )

    # Filter to genuinely new posts (not already in the sheet)
    known      = existing_urls or set()
    new_posts  = [p for p in all_posts if p.get("url", "") not in known]

    if progress_callback:
        skipped = len(all_posts) - len(new_posts)
        msg = f"Found {len(new_posts)} new founder posts"
        if skipped:
            msg += f" ({skipped} already saved, skipped)"
        await progress_callback(msg + ". Saving to Sheets...")

    today = str(date.today())
    for post in new_posts:
        try:
            append_row("Jobs", [
                today,
                post.get("post_date", "Unknown"),
                post.get("company", "Unknown"),
                post.get("role_hiring", ""),
                "N/A",
                "Remote / Unknown",
                post.get("source", "Social"),
                post.get("url", ""),
                post.get("contact_method", ""),
                post.get("post_snippet", ""),
                role,
                "New",
                "Social Post",
                post.get("match_score", 50),
            ])
        except Exception as e:
            logger.warning(f"Failed to save social post to Sheets: {e}")

    if progress_callback:
        top = new_posts[0] if new_posts else {}
        await progress_callback(
            f"Social scan done. {len(new_posts)} new founder posts saved."
            + (f" Top: {top.get('company', '')} ({top.get('match_score', 0)}/100)." if top else "")
        )

    return new_posts
