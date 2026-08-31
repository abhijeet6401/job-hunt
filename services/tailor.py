"""
Resume tailoring: given a JD and role type, rewrites bullet points in a base LaTeX resume
to better match the job description, then compiles to PDF.

Input: jd_text (string), role_type (string), groq_api_key (string).
Output: dict with 'pdf_bytes', 'diff' (list of before/after pairs), 'latex' (final LaTeX).

Rules:
- Never add skills or experience not present in the base resume.
- Never remove core metrics (revenue numbers, percentages, named achievements).
- Only adjust emphasis and language of 3 most relevant bullet points.
"""

import os
import json
import logging
from datetime import date

from groq import Groq

from services.pdf_compiler import compile_latex
from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

ROLE_TO_FILE = {
    "product": "resumes/product.tex",
    "founders_office": "resumes/founders_office.tex",
    "data_analyst": "resumes/data_analyst.tex",
    "operations": "resumes/operations.tex",
}


def _load_resume(role_type: str) -> str:
    """Load the base LaTeX resume file for a given role type."""
    path = ROLE_TO_FILE.get(role_type)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            f"Resume file not found for role '{role_type}'. "
            f"Expected at: {path}. Add your LaTeX resume content to this file."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _detect_role(groq_client: Groq, jd_text: str) -> str:
    """
    Use Groq to determine which of the four role types best matches a job description.

    Returns one of: product, founders_office, data_analyst, operations.
    """
    prompt = f"""
Given this job description, which role category is the best match?
Categories: product, founders_office, data_analyst, operations

Reply with exactly one word from the list above. No explanation.

Job description:
{jd_text[:2000]}
"""
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    detected = response.choices[0].message.content.strip().lower()
    if detected not in ROLE_TO_FILE:
        return "product"
    return detected


def _extract_keywords(groq_client: Groq, jd_text: str) -> list[str]:
    """
    Extract the top 8 keywords and requirements from a job description.

    Returns a list of keyword/phrase strings.
    """
    prompt = f"""
Extract the 8 most important keywords and requirements from this job description.
Focus on: skills, tools, responsibilities, and qualities they're explicitly looking for.
Return a JSON array of strings. No explanation, no markdown.

Job description:
{jd_text[:3000]}
"""
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end])
    except Exception:
        return []


def _rewrite_bullets(groq_client: Groq, latex_source: str, keywords: list[str], jd_text: str) -> tuple[str, list[dict]]:
    """
    Identify and rewrite 3 bullet points in the LaTeX resume to better match the JD.

    Returns (modified_latex_string, diff_list) where diff_list is a list of
    {'before': str, 'after': str} dicts for display in the UI.

    Strict rules enforced via prompt:
    - Only rephrase, never fabricate.
    - Preserve all numbers, company names, and measurable outcomes.
    - Only touch \\item lines.
    """
    keywords_str = ", ".join(keywords)

    prompt = f"""
You are tailoring a LaTeX resume to better match a specific job description.

STRICT RULES:
1. Identify the 3 \\item bullet points in the LaTeX that are MOST RELEVANT to this job.
2. Rewrite ONLY those 3 bullets to emphasize the keywords listed below.
3. NEVER add skills, tools, or experience not already present.
4. NEVER remove or change any numbers, percentages, revenue figures, or named achievements.
5. NEVER change \\item lines that are not one of your chosen 3.
6. Keep LaTeX formatting identical — only change the text content inside \\item.

Keywords to emphasize: {keywords_str}

Return a JSON object with:
- "modified_latex": the complete LaTeX source with exactly 3 \\item lines changed
- "diff": array of 3 objects, each with "before" and "after" keys (plain text, no LaTeX commands)

Job description summary:
{jd_text[:1500]}

LaTeX resume:
{latex_source}
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        modified_latex = parsed.get("modified_latex", latex_source)
        diff = parsed.get("diff", [])
        return modified_latex, diff
    except Exception as e:
        logger.error(f"Failed to parse Groq rewrite response: {e}")
        return latex_source, []


def _summarize_jd(groq_client: Groq, jd_text: str) -> str:
    """Return a 2-3 line summary of the job description for Sheets logging."""
    prompt = f"Summarize this job description in 2-3 sentences (max 50 words). Focus on role, company type, and key requirements:\n\n{jd_text[:1500]}"
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def tailor_resume(
    jd_text: str,
    role_type: str,
    company_name: str,
    groq_api_key: str,
    role_title: str = "",
) -> dict:
    """
    Full resume tailoring pipeline.

    1. Auto-detect role if role_type == 'auto'
    2. Load base LaTeX for that role
    3. Extract top 8 keywords from JD
    4. Rewrite 3 most relevant bullet points
    5. Compile to PDF
    6. Log to Google Sheets Applications tab
    7. Return pdf_bytes, diff, latex, and resolved role_type
    """
    groq_client = Groq(api_key=groq_api_key)

    if role_type == "auto":
        role_type = _detect_role(groq_client, jd_text)
        logger.info(f"Auto-detected role type: {role_type}")

    latex_source = _load_resume(role_type)
    keywords = _extract_keywords(groq_client, jd_text)
    logger.info(f"Extracted keywords: {keywords}")

    modified_latex, diff = _rewrite_bullets(groq_client, latex_source, keywords, jd_text)
    pdf_bytes = compile_latex(modified_latex)

    jd_summary = _summarize_jd(groq_client, jd_text)
    today = str(date.today())
    pdf_filename = f"{today}_{company_name.replace(' ', '_')}_{role_type}.pdf"

    # Summarise what the AI actually changed for the "Key Changes Made" column
    key_changes = "; ".join([
        f"{d.get('before', '')[:60]}... → {d.get('after', '')[:60]}..."
        for d in diff
    ]) if diff else "No diff captured"

    try:
        append_row("Applications", [
            today,                          # Date
            company_name,                   # Company
            role_title or role_type,        # Role Title
            role_type,                      # Role Type
            jd_summary,                 # JD Summary (2-3 lines)
            f"{role_type}.tex",         # Resume Version Used
            key_changes,                # Key Changes Made
            pdf_filename,               # PDF Filename
            "Tailored",                 # Status
        ])
    except Exception as e:
        logger.warning(f"Failed to log to Sheets: {e}")

    return {
        "pdf_bytes": pdf_bytes,
        "diff": diff,
        "latex": modified_latex,
        "role_type": role_type,
        "keywords": keywords,
        "pdf_filename": pdf_filename,
    }
