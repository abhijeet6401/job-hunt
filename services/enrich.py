"""
Job enrichment: deep info for a single job card, fetched lazily as it reaches
the front of the swipe deck.

Two sources, one Groq synthesis call:
  1. Tavily extract on the job URL  → full job description text.
  2. Tavily search on the company   → funding, team size, founders, recent news.

Output is a structured dict the frontend renders inside the card:
  company_snapshot: {what_they_do, funding, team_size, founders, recent_news}
  jd_digest:        {responsibilities[], requirements[], nice_to_have[], red_flags[]}
  fit_note:         one sentence on why this is / isn't a fit for the candidate.
"""

import os
import json
import logging

from groq import Groq
from tavily import TavilyClient

logger = logging.getLogger(__name__)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")

_EMPTY = {
    "company_snapshot": {
        "what_they_do": "", "funding": "", "team_size": "",
        "founders": "", "recent_news": "",
    },
    "jd_digest": {
        "responsibilities": [], "requirements": [],
        "nice_to_have": [], "red_flags": [],
    },
    "fit_note": "",
}


def _fetch_jd_text(tavily_client: TavilyClient, url: str) -> str:
    """Pull the full page text of the job posting via Tavily extract."""
    if not url:
        return ""
    try:
        response = tavily_client.extract(urls=[url])
        results = response.get("results", [])
        if results:
            return results[0].get("raw_content", "") or ""
    except Exception as e:
        logger.warning(f"Tavily extract failed for '{url}': {e}")
    return ""


def _fetch_company_snippets(tavily_client: TavilyClient, company: str) -> str:
    """Search for company facts: stage, funding, founders, size, news."""
    if not company or company.lower() in ("unknown", ""):
        return ""
    query = f'"{company}" startup funding founders team size news'
    try:
        response = tavily_client.search(query=query, max_results=4, search_depth="basic")
        return " ".join(
            r.get("title", "") + ": " + r.get("content", "")
            for r in response.get("results", [])
        )
    except Exception as e:
        logger.warning(f"Company snapshot search failed for '{company}': {e}")
        return ""


def enrich_job(
    url: str,
    company: str,
    role: str,
    groq_api_key: str,
    tavily_api_key: str,
) -> dict:
    """
    Build the enrichment payload for one job. Returns _EMPTY-shaped dict on failure
    so the frontend can always render the section without null checks.
    """
    groq_client   = Groq(api_key=groq_api_key)
    tavily_client = TavilyClient(api_key=tavily_api_key)

    jd_text  = _fetch_jd_text(tavily_client, url)
    snippets = _fetch_company_snippets(tavily_client, company)

    if not jd_text and not snippets:
        return dict(_EMPTY)

    prompt = f"""You are enriching a job card for a candidate deciding whether to apply.

Candidate: 22-year-old technical founder (built an AI platform with 300 paying users),
targeting PM / APM / Founder's Office / Data Analyst / Ops roles at seed-Series B startups,
0 years formal full-time experience, based in Bangalore, open to remote.

Job: {role or "Unknown role"} at {company or "Unknown company"}

Company research snippets:
{snippets[:3000] or "(none found)"}

Job posting page text:
{jd_text[:5000] or "(could not fetch)"}

Return ONLY a JSON object with exactly these keys:
{{
  "company_snapshot": {{
    "what_they_do": "one sentence",
    "funding": "e.g. 'Series A, $12M (2025)' or 'Unknown'",
    "team_size": "e.g. '~40 people' or 'Unknown'",
    "founders": "names if found, else 'Unknown'",
    "recent_news": "one notable recent item, or ''"
  }},
  "jd_digest": {{
    "responsibilities": ["max 4 short bullets"],
    "requirements": ["max 4 short bullets"],
    "nice_to_have": ["max 3 short bullets"],
    "red_flags": ["things that hurt this candidate's chances, e.g. '5+ yrs required'; max 3"]
  }},
  "fit_note": "one blunt sentence: why this candidate should or shouldn't apply"
}}

Use only facts present in the text above. Empty string / empty array when unknown."""

    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1,
            )
            raw   = response.choices[0].message.content.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return dict(_EMPTY)
            data = json.loads(raw[start:end])
            out  = dict(_EMPTY)
            snap = data.get("company_snapshot", {}) or {}
            dig  = data.get("jd_digest", {}) or {}
            out["company_snapshot"] = {k: str(snap.get(k, "") or "") for k in out["company_snapshot"]}
            out["jd_digest"] = {
                k: [str(x) for x in (dig.get(k) or [])][:4]
                for k in out["jd_digest"]
            }
            out["fit_note"] = str(data.get("fit_note", "") or "")
            return out
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                import time
                time.sleep(3.0 * (attempt + 1))
                continue
            logger.error(f"Groq enrichment failed for '{company}': {e}")
            return dict(_EMPTY)
    return dict(_EMPTY)
