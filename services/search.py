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

import os
import time
import asyncio
import json
import logging
from datetime import date

from groq import Groq
from tavily import TavilyClient

from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")


def _safe_chat_completion(groq_client: Groq, **kwargs):
    """Execute chat completion with automatic retry on 429 rate limits."""
    for attempt in range(3):
        try:
            return groq_client.chat.completions.create(**kwargs)
        except Exception as e:
            if ("429" in str(e) or "rate_limit" in str(e).lower()) and attempt < 2:
                wait_secs = 3.5 * (attempt + 1)
                logger.info(f"Groq 429 rate limit hit. Waiting {wait_secs}s before retry...")
                time.sleep(wait_secs)
                continue
            raise e

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
    "product":         '("product manager" OR "APM" OR "associate product manager")',
    "founders_office": '("founder\'s office" OR "chief of staff" OR "founders office" OR generalist OR "venture capital")',
    "data_analyst":    '("data analyst" OR "business analyst" OR "product analyst" OR "data scientist")',
    "operations":      '("operations" OR "biz ops" OR "business operations" OR "growth ops")',
    "finance":         '("investment analyst" OR "venture capital" OR "equity research" OR "financial analyst")',
    "all":             '(product OR "APM" OR "founder office" OR "chief of staff" OR "data analyst" OR "investment analyst" OR "biz ops")',
}

# ── Dedicated Y Combinator queries (WorkAtAStartup, YC Companies, Bookface, HN)
YC_QUERY_TEMPLATES = [
    "site:workatastartup.com/jobs {kw}",
    "site:ycombinator.com/companies/*/jobs {kw}",
    "site:ycombinator.com/jobs {kw}",
    '"Y Combinator" ("hiring" OR "join our team" OR "join us") {kw} ("India" OR "remote" OR "Bengaluru" OR "Bangalore")',
    '("YC W24" OR "YC S24" OR "YC W25" OR "YC S25" OR "YC W26") ("hiring" OR "join") {kw}',
    'site:wellfound.com/jobs "Y Combinator" {kw}',
]

# Tier 1: startup job boards
TIER1_QUERY_TEMPLATES = [
    'site:wellfound.com/jobs {kw} ("startup" OR "seed" OR "series a")',
    'site:linkedin.com/jobs {kw} startup ("India" OR "remote" OR "Bangalore")',
    'site:linkedin.com/jobs ("0-2 years" OR "fresher" OR "associate" OR "new grad") {kw}',
    'site:cutshort.io {kw} ("startup" OR "Bangalore" OR "remote")',
    'site:instahyre.com {kw} ("startup" OR "Bangalore" OR "remote")',
    'site:peerlist.io/jobs {kw}',
]

# Tier 2: founder-activity signals — static fallback when LLM query generation fails
TIER2_FALLBACK_QUERIES = [
    'site:linkedin.com/posts "just closed" OR "seed round" startup hiring product',
    'site:linkedin.com/posts "we are a team of" startup "looking for" product',
    'site:x.com "we are hiring" startup "product manager" OR "APM" ("DM" OR "apply")',
    'site:twitter.com "join us" startup "product manager" OR "generalist"',
]


def _yc_queries(role: str) -> list[str]:
    """Build dedicated Y Combinator queries for the selected role."""
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    return [t.format(kw=kw) for t in YC_QUERY_TEMPLATES]


def _tier1_queries(role: str) -> list[str]:
    """Build the per-source tier-1 query list for the selected role filter."""
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    return [t.format(kw=kw) for t in TIER1_QUERY_TEMPLATES]


def _social_queries_for_role(role: str) -> list[str]:
    """Build targeted founder hiring post queries for LinkedIn and X/Twitter."""
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    return [
        # YC Founders hiring on X & LinkedIn
        f'site:x.com ("YC" OR "Y Combinator") ("we\'re hiring" OR "I\'m hiring" OR "join us") {kw} ("DM" OR "apply")',
        f'site:twitter.com ("YC" OR "Y Combinator") ("we\'re hiring" OR "I\'m hiring") {kw} ("DM" OR "reach out")',
        f'site:linkedin.com/posts ("YC" OR "Y Combinator") ("hiring" OR "join our team") {kw} ("DM" OR "apply")',
        # Direct Founder hiring posts on LinkedIn
        f'site:linkedin.com/posts ("we\'re hiring" OR "I\'m hiring") {kw} ("DM me" OR "email" OR "send your CV" OR "send resume")',
        f'site:linkedin.com/posts ("hiring our first" OR "looking for our founding" OR "founding APM" OR "founding PM") {kw} ("DM" OR "reach out")',
        f'site:linkedin.com/posts "join our team" {kw} ("startup" OR "seed" OR "series a") ("India" OR "Bangalore" OR "remote")',
        f'site:linkedin.com/posts "just raised" "hiring" {kw} ("DM" OR "reach out" OR "email")',
        # Direct Founder posts on X / Twitter
        f'site:x.com ("we\'re hiring" OR "I\'m hiring") {kw} ("DM" OR "apply" OR "reach out")',
        f'site:twitter.com ("we\'re hiring" OR "I\'m hiring") {kw} ("DM" OR "apply" OR "email")',
        f'site:x.com ("looking for an APM" OR "looking for a PM" OR "founding PM" OR "founding APM") ("DM" OR "reach out")',
        f'site:x.com ("hiring a generalist" OR "hiring chief of staff" OR "founding member") {kw} ("DM" OR "reach out")',
        f'site:linkedin.com/posts "we are hiring" {kw} ("India" OR "Bangalore" OR "Bengaluru" OR "remote")',
    ]


def _generate_tier2_queries(groq_client: Groq, role: str) -> list[str]:
    """
    Ask Groq for fresh founder-activity-signal queries so each refresh explores
    different phrasing instead of replaying the same fixed list.
    """
    kw = ROLE_KEYWORDS.get(role, ROLE_KEYWORDS["all"])
    prompt = f"""Generate 5 web search queries to find startup hiring signals posted by founders.
Role to match: {kw}.
Target: posts by founders/executives on LinkedIn (site:linkedin.com/posts) and Twitter/X (site:x.com or site:twitter.com)
announcing open roles. Prefer India or remote.
Vary the hiring phrasing across queries (e.g. "we're hiring", "looking for our first", "join us as", "just raised ... hiring", "DM me if").
Return ONLY a JSON array of 5 query strings."""
    try:
        response = _safe_chat_completion(
            groq_client,
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


def _run_tavily_query(
    client: TavilyClient,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    days: int = None,
) -> list[dict]:
    """Run a single Tavily search."""
    try:
        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if days is not None:
            kwargs["days"] = days
        response = client.search(**kwargs)
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


JUNK_URL_SUBSTRINGS = [
    "/pulse/", "/article/", "/articles/", "/news/", "/blog/", "/blogs/",
    "/guides/", "/guide/", "/questions/", "/interview-questions/",
    "/courses/", "/course/", "/podcast/", "/podcasts/", "/salary/",
    "/trends/", "/insights/", "/resources/", "/sample-resume/",
    "/resume-tips/", "/resume-examples/", "/books/", "/events/",
    "/webinar/", "/community/", "/forum/", "/discussion/"
]

JUNK_TITLE_SUBSTRINGS = [
    "interview questions", "how to become", "career path", "salary guide",
    "resume tips", "resume sample", "what is a", "top 10", "top 5",
    "top 20", "hiring trends", "market report", "key trends", "guide to",
    "tips for", "advice for", "preparation", "prep guide", "cheat sheet",
    "syllabus", "course review", "certification", "books for"
]


def _is_junk_job(url: str, title: str = "", summary: str = "") -> bool:
    """Detect non-job content like blogs, articles, interview prep guides, and salary surveys."""
    u = url.lower()
    for sub in JUNK_URL_SUBSTRINGS:
        if sub in u:
            return True
    t = (title + " " + summary).lower()
    for sub in JUNK_TITLE_SUBSTRINGS:
        if sub in t:
            return True
    return False


def _detect_is_yc(url: str, title: str = "", snippet: str = "", company: str = "") -> bool:
    """Check if a job or post is associated with Y Combinator."""
    text = f"{url} {title} {snippet} {company}".lower()
    yc_indicators = [
        "workatastartup.com", "ycombinator.com", "y combinator",
        "yc w24", "yc s24", "yc w25", "yc s25", "yc w26", "yc s26",
        "yc w23", "yc s23", "yc-backed", "yc backed", "yc company"
    ]
    return any(ind in text for ind in yc_indicators)


def _extract_job_fields_only(groq_client: Groq, raw_results: list[dict]) -> list[dict]:
    """
    Call 1 of 2: extract structured fields from a batch of raw Tavily results.
    Strictly filters out non-job content and auto-tags Y Combinator openings.
    Does NOT score — scoring is a separate dedicated call.
    """
    if not raw_results:
        return []

    # Pre-filter out blatant non-job URLs
    filtered_results = [
        r for r in raw_results
        if not _is_junk_job(r.get("url", ""), r.get("title", ""), r.get("content", ""))
    ]
    if not filtered_results:
        return []

    batch_text = "\n\n---\n\n".join([
        f"URL: {r.get('url', '')}\nTitle: {r.get('title', '')}\nSnippet: {r.get('content', '')}"
        for r in filtered_results
    ])

    prompt = f"""You are an elite job discovery extraction engine.

Extract structured job opening data from the search results below.

CRITICAL RULES:
1. ONLY include open, real job opportunities.
2. REJECT news articles, press releases, blogs, and industry trend reports (e.g., 'startup raises $5M', 'hiring trends in 2026', 'market analysis').
3. REJECT career advice, interview questions, resume templates, and tutorials.
4. REJECT aggregator landing pages or directory index pages that do not list a specific open role.
5. If a post is closed, expired, or position is filled, set is_open: false.
6. If the company is a Y Combinator startup or URL is from workatastartup.com or ycombinator.com, set source: "Y Combinator" and is_yc: true.

For each search result, output a JSON array. Each element must have these exact keys:
- company:     string  (company name, or "Unknown")
- role:        string  (job title as listed)
- salary:      string  (e.g. "8-12 LPA", "USD 60k-80k", or "Not mentioned")
- location:    string  (e.g. "Remote", "Bangalore", "Hybrid - Mumbai")
- source:      string  (LinkedIn / Wellfound / WorkAtAStartup / Y Combinator / Web)
- is_yc:       boolean (true if Y Combinator / WorkAtAStartup company)
- summary:     string  (one sentence: what the company does and its stage)
- url:         string  (URL from the result)
- is_job:      boolean (true only if this is a real, open job posting — not a blog, news, or advice)
- is_open:     boolean (false if filled, closed, expired, or past application deadline)
- date_posted: string  (posting date if visible, e.g. "2026-06-05"; otherwise "Unknown")

Only include entries where is_job is true. Return only a valid JSON array. No other text.

Search results:
{batch_text}"""

    try:
        response = _safe_chat_completion(
            groq_client,
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
            url = j.get("url", "")
            role = j.get("role", "")
            summary = j.get("summary", "")
            company = j.get("company", "")
            if _is_junk_job(url, role, summary):
                logger.info(f"Filtered junk job/article: {url}")
                continue
            if _detect_is_yc(url, role, summary, company):
                j["is_yc"] = True
                if not j.get("source") or j.get("source") in ("Web", "Job Board", "Unknown"):
                    j["source"] = "Y Combinator"
            else:
                j["is_yc"] = j.get("is_yc", False)
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
        response = _safe_chat_completion(
            groq_client,
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


def _is_valid_social_post(post: dict) -> bool:
    """Strictly validate that a result is a genuine social media hiring post."""
    if not post.get("is_hiring_post", False):
        return False

    url = (post.get("url") or "").strip().lower()
    # Must be LinkedIn or X/Twitter
    is_linkedin = "linkedin.com" in url
    is_twitter  = "x.com" in url or "twitter.com" in url
    if not (is_linkedin or is_twitter):
        return False

    # LinkedIn checks
    if is_linkedin:
        # Must be a post/feed update, NOT a pulse article, job listing, learning, or generic company page
        if "/pulse/" in url or "/learning/" in url or "/jobs/" in url:
            return False
        if not ("/posts/" in url or "/feed/update/" in url):
            return False

    # Twitter/X checks
    if is_twitter:
        # Must be a specific status/tweet
        if "/status/" not in url:
            return False

    role = (post.get("role_hiring") or "").strip().lower()
    if not role or role in ("unknown", "n/a", "none", "?"):
        return False
    # Reject non-role values like "advice", "tips", "article", "seeking a role"
    junk_roles = ["tip", "advice", "guide", "article", "seeking", "looking for job", "open to work", "course", "interview", "questions"]
    if any(jr in role for jr in junk_roles):
        return False

    snippet = (post.get("post_snippet") or "").lower()
    # Reject if it's someone looking for a job themselves
    job_seeker_phrases = [
        "i am looking for a job", "looking for new opportunities", "open to work",
        "recently laid off", "seeking a role as", "actively looking for", "my resume attached",
        "please hire me", "looking for an internship for myself"
    ]
    if any(phrase in snippet for phrase in job_seeker_phrases):
        return False

    # Reject educational/marketing posts
    educational_phrases = [
        "in this article", "here are 5 tips", "read full breakdown", "check out my newsletter",
        "how i cracked", "top books", "salary survey results", "top 10 questions"
    ]
    if any(phrase in snippet for phrase in educational_phrases):
        return False

    return True


def _extract_social_fields(groq_client: Groq, raw_results: list[dict]) -> list[dict]:
    """
    Extract structured social-post hiring data from a batch of Tavily results.

    Returns entries where a founder/hiring manager is directly posting about an open role,
    with candidate match scoring identical to the job board pipeline.
    """
    if not raw_results:
        return []

    # Pre-filter raw URLs to ensure they look like actual posts
    valid_raw = []
    for r in raw_results:
        u = (r.get("url") or "").lower()
        if "/pulse/" in u or "/jobs/" in u or "/learning/" in u:
            continue
        if "linkedin.com" in u and not ("/posts/" in u or "/feed/update/" in u):
            continue
        if ("x.com" in u or "twitter.com" in u) and "/status/" not in u:
            continue
        valid_raw.append(r)

    if not valid_raw:
        return []

    batch_text = "\n\n---\n\n".join([
        f"URL: {r.get('url', '')}\nTitle: {r.get('title', '')}\nSnippet: {r.get('content', '')}"
        for r in valid_raw
    ])

    prompt = f"""
{CANDIDATE_PROFILE}

You are extracting structured hiring data from direct founder and executive social media posts (LinkedIn, Twitter/X).

CRITICAL CRITERIA:
1. This MUST be a personal social post from a human (Founder, Co-Founder, CEO, CTO, VP, or Hiring Manager) stating that THEIR company is actively hiring for a specific role and asking people to apply or reach out.
2. REJECT career advice, interview tips, resume coaching, or thought leadership ("Here are 5 tips for PMs", "How to break into tech").
3. REJECT news articles, funding announcements, or podcast promos without a direct hiring call.
4. REJECT job seekers advertising their own availability ("I am looking for a role", "open to work").
5. REJECT recruiter agencies posting generic client listings.

For each result below, output a JSON array. Each element must have these exact keys:
- poster_name:    string  (name of the person who posted, or "Unknown")
- poster_role:    string  (their role: "Co-Founder", "CTO", "Founder", "HR Manager", "Unknown")
- company:        string  (company name, or "Unknown")
- role_hiring:    string  (role they are hiring for, e.g. "Product Manager", "APM", "Founding Engineer")
- contact_method: string  (how to apply: "DM on LinkedIn", "Email: x@y.com", "Link in bio", "Unknown")
- is_founder_post: boolean (true if poster is founder/co-founder/CTO/CEO — NOT an HR recruiter)
- is_yc:          boolean (true if poster/company mentions Y Combinator, YC, or WorkAtAStartup)
- post_date:      string  (post date if visible, e.g. "2026-06-05"; otherwise "Unknown")
- url:            string  (URL from the result)
- post_snippet:   string  (1-2 sentences summarising what the post says about the role/company)
- source:         string  ("LinkedIn" / "Twitter" / "X" / "Web")
- match_score:    integer (1-100, candidate fit score)
- score_reason:   string  (short phrase, e.g. "YC AI startup, founder post, 0-2yr exp, India")
- is_hiring_post: boolean (true ONLY if this is a genuine hiring post from a founder/hiring manager)

Scoring guidance:
- 85-100: YC or top seed startup, role is PM/APM/Founder's Office/Strategy, direct founder post, India or remote
- 70-84:  Good match at early-stage startup, direct hiring manager post
- 50-69:  Mid-sized company or adjacent function
- <50:    Enterprise, senior-only, or not a genuine hiring post

Only include entries where is_hiring_post is true. Return only a valid JSON array. No other text.

Search results:
{batch_text}
"""

    try:
        response = _safe_chat_completion(
            groq_client,
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
            if not _is_valid_social_post(p):
                continue
            url = p.get("url", "")
            role = p.get("role_hiring", "")
            snip = p.get("post_snippet", "")
            comp = p.get("company", "")
            if _detect_is_yc(url, role, snip, comp):
                p["is_yc"] = True
            else:
                p["is_yc"] = p.get("is_yc", False)
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
        response = _safe_chat_completion(
            groq_client,
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
    Two-tier job discovery pipeline with dedicated Y Combinator scanning.

    Tier 1 + YC:
      - 6 dedicated Y Combinator queries (WorkAtAStartup, YC Companies, Bookface)
      - 6 high-signal startup board queries (Wellfound, LinkedIn, Cutshort, Instahyre, Peerlist)
      - Stream high-signal & YC results to UI immediately via SSE tier1_result event.
    Tier 2:
      - LLM-generated founder-activity signals.
    Combined:
      - Company deduplication, recruiter email lookup, Sheets save.
    """
    groq_client   = Groq(api_key=groq_api_key)
    tavily_client = TavilyClient(api_key=tavily_api_key)
    loop          = asyncio.get_event_loop()
    known         = existing_urls or set()
    batch_size    = 10

    # ── Tier 1 + Y Combinator queries ────────────────────────────────────────
    yc_queries    = _yc_queries(role)
    tier1_queries = _tier1_queries(role)
    total_q_count = len(yc_queries) + len(tier1_queries)

    if progress_callback:
        await progress_callback(
            f"Scanning Y Combinator & high-signal startup boards ({total_q_count} searches)..."
        )

    # Run YC queries (days=None so active WorkAtAStartup & YC listings are never dropped)
    yc_tasks = [
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q, 5, "advanced", None)
        for q in yc_queries
    ]
    # Run Tier 1 queries (days=14 for fresh startup board listings)
    tier1_tasks = [
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q, 5, "advanced", 14)
        for q in tier1_queries
    ]

    all_raw_batches = await asyncio.gather(*(yc_tasks + tier1_tasks))
    all_raw = [r for batch in all_raw_batches for r in batch]
    unique_raw = _url_deduplicate(all_raw)

    if progress_callback:
        await progress_callback(
            f"{len(unique_raw)} unique openings found (YC + Top Boards). Extracting and scoring..."
        )

    tier1_jobs: list[dict] = []
    for i in range(0, len(unique_raw), batch_size):
        batch = unique_raw[i : i + batch_size]
        jobs  = await loop.run_in_executor(None, _extract_job_fields, groq_client, batch)
        tier1_jobs.extend(jobs)
        if progress_callback:
            await progress_callback(f"Scored {len(tier1_jobs)} jobs so far...")

    tier1_jobs = _company_deduplicate(tier1_jobs)
    # Sort: YC startups first, then match_score descending
    tier1_jobs.sort(key=lambda j: (j.get("is_yc", False), j.get("match_score", 0)), reverse=True)
    tier1_urls = {j.get("url", "") for j in tier1_jobs}

    # Stream tier-1 + YC results immediately
    tier1_new = [j for j in tier1_jobs if j.get("url", "") not in known]
    if progress_callback and tier1_new:
        await progress_callback(json.dumps({
            "type": "tier1_result",
            "jobs": tier1_new,
        }))
        yc_found = sum(1 for j in tier1_new if j.get("is_yc"))
        await progress_callback(
            f"Showing {len(tier1_new)} high-signal results ({yc_found} YC startups). "
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
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q, 5, "basic", 14)
        for q in tier2_queries
    ])
    tier2_raw = [r for batch in tier2_raw_nested for r in batch]
    tier2_raw = [r for r in tier2_raw if r.get("url", "") not in tier1_urls]
    tier2_unique = _url_deduplicate(tier2_raw)

    if progress_callback:
        await progress_callback(
            f"{len(tier2_unique)} new founder signal results. Extracting and scoring..."
        )

    tier2_jobs: list[dict] = []
    for i in range(0, len(tier2_unique), batch_size):
        batch = tier2_unique[i : i + batch_size]
        jobs  = await loop.run_in_executor(None, _extract_job_fields, groq_client, batch)
        tier2_jobs.extend(jobs)

    # ── Combine, dedup, sort ─────────────────────────────────────────────────
    all_jobs = _company_deduplicate(tier1_jobs + tier2_jobs)
    all_jobs.sort(key=lambda j: (j.get("is_yc", False), j.get("match_score", 0)), reverse=True)

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
        yc_total = sum(1 for j in new_jobs if j.get("is_yc"))
        await progress_callback(
            f"Done. {len(new_jobs)} new jobs saved ({yc_total} YC startups). "
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
    Social Job Scanner: discover genuine roles posted directly by founders on LinkedIn/X.

    1.  Targeted parallel Tavily queries targeting LinkedIn/Twitter/X hiring posts.
    2.  URL-level deduplication.
    3.  Groq extraction with strict criteria (rejects articles, advice, news, and job seekers).
    4.  Strict validation via _is_valid_social_post.
    5.  Sort: YC founder posts first, then recency tier (≤3d / ≤7d / ≤14d / older), then match_score.
    6.  Save to Google Sheets Jobs tab (Source Type = "Social Post").
    7.  Return only new posts.
    """
    groq_client   = Groq(api_key=groq_api_key)
    tavily_client = TavilyClient(api_key=tavily_api_key)
    loop          = asyncio.get_event_loop()

    social_queries = _social_queries_for_role(role)

    if progress_callback:
        await progress_callback(
            f"Scanning {len(social_queries)} targeted founder queries across LinkedIn & X..."
        )

    raw_nested = await asyncio.gather(*[
        loop.run_in_executor(None, _run_tavily_query, tavily_client, q, 5, "advanced", 14)
        for q in social_queries
    ])

    all_raw = [r for batch in raw_nested for r in batch]

    if progress_callback:
        await progress_callback(f"Got {len(all_raw)} candidate posts. Filtering and deduplicating...")

    unique_raw = _url_deduplicate(all_raw)

    if progress_callback:
        await progress_callback(
            f"{len(unique_raw)} unique posts to verify. Extracting founder hiring calls..."
        )

    batch_size = 10
    all_posts  = []
    for i in range(0, len(unique_raw), batch_size):
        batch = unique_raw[i : i + batch_size]
        posts = await loop.run_in_executor(None, _extract_social_fields, groq_client, batch)
        all_posts.extend(posts)

    # Strict post-processing validation: must be a genuine founder/executive hiring post
    valid_posts = [p for p in all_posts if _is_valid_social_post(p)]

    # Sort: YC posts first, then recency tier (ascending) then match_score (descending)
    valid_posts.sort(
        key=lambda p: (
            not p.get("is_yc", False),
            _recency_tier(p.get("post_date", "Unknown")),
            -p.get("match_score", 0)
        )
    )

    # Filter to genuinely new posts (not already in the sheet)
    known      = existing_urls or set()
    new_posts  = [p for p in valid_posts if p.get("url", "") not in known]

    if progress_callback:
        skipped = len(valid_posts) - len(new_posts)
        msg = f"Found {len(new_posts)} genuine founder hiring posts"
        if skipped:
            msg += f" ({skipped} already saved, skipped)"
        await progress_callback(msg + ". Saving to Sheets...")

    today = str(date.today())
    for post in new_posts:
        try:
            source_label = "Y Combinator Founder" if post.get("is_yc") else post.get("source", "Social")
            append_row("Jobs", [
                today,
                post.get("post_date", "Unknown"),
                post.get("company", "Unknown"),
                post.get("role_hiring", ""),
                "N/A",
                "Remote / Unknown",
                source_label,
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
        yc_count = sum(1 for p in new_posts if p.get("is_yc"))
        await progress_callback(
            f"Social scan done. {len(new_posts)} verified founder posts saved ({yc_count} YC founders)."
            + (f" Top: {top.get('company', '')} ({top.get('match_score', 0)}/100)." if top else "")
        )

    return new_posts
