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
import re
import json
import logging
from datetime import date

from groq import Groq

from services.pdf_compiler import compile_latex
from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")

ROLE_TO_FILE = {
    "product": "resumes/product.tex",
    "founders_office": "resumes/founders_office.tex",
    "data_analyst": "resumes/data_analyst.tex",
    "operations": "resumes/operations.tex",
    "finance": "resumes/finance_investing.tex",
}


def _load_resume(role_type: str) -> str:
    path = ROLE_TO_FILE.get(role_type, ROLE_TO_FILE["product"])
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _detect_role(groq_client: Groq, jd_text: str) -> str:
    """
    Use Groq to determine which role category best matches a job description.

    Returns one of: product, founders_office, data_analyst, operations, finance.
    """
    prompt = f"""
Given this job description, which role category is the best match?
Categories: product, founders_office, data_analyst, operations, finance

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
    """
    import re
    keywords_str = ", ".join(keywords)

    bullets = re.findall(r'\\achieve\{(.*?)\}', latex_source, flags=re.DOTALL)
    if not bullets:
        bullets = re.findall(r'\\item\s+(.*?)(?=\\item|\\end|\Z)', latex_source, flags=re.DOTALL)

    bullets_clean = [b.strip() for b in bullets if b.strip()]
    numbered_bullets = "\n".join([f"{i+1}. {b}" for i, b in enumerate(bullets_clean)])

    prompt = f"""You are tailoring resume bullets to match a job description.
Keywords to emphasize: {keywords_str}

Job Description:
{jd_text[:1500]}

Candidate's Current Bullets:
{numbered_bullets}

Select the 3 most relevant bullets. Rewrite them to emphasize the keywords.
STRICT RULES:
1. NEVER fabricate experience, tools, or skills not already present.
2. NEVER change any numbers, percentages, revenue figures, or named achievements.
3. Keep LaTeX formatting intact (e.g. \\%, \\&, \\$).
4. Ensure the tailored bullets are rich, completely filled with context, action verbs, and quantifiable outcomes. Do NOT shorten, skip, or summarize.
5. Return a valid JSON object with key 'diff': a list of exactly 3 objects, each with:
   - "before": the exact text of the chosen original bullet
   - "after": the tailored version of the bullet
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        diff = data.get("diff", [])
        if not isinstance(diff, list):
            diff = []

        from services.pdf_compiler import sanitize_unicode

        modified_latex = latex_source
        for item in diff:
            before = item.get("before", "").strip()
            after = sanitize_unicode(item.get("after", "").strip())
            item["after"] = after
            if not before or not after:
                continue
            if before in modified_latex:
                modified_latex = modified_latex.replace(before, after, 1)
            else:
                for b in bullets_clean:
                    if b[:35] in before or before[:35] in b:
                        modified_latex = modified_latex.replace(b, after, 1)
                        break
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
    try:
        pdf_bytes = compile_latex(modified_latex)
    except Exception as e:
        logger.warning(f"Error compiling PDF: {e}")
        pdf_bytes = compile_latex(latex_source)

    jd_summary = _summarize_jd(groq_client, jd_text)
    today = str(date.today())
    safe_company = re.sub(r'[^a-zA-Z0-9_-]', '_', company_name) or "Company"
    pdf_filename = f"{today}_{safe_company}_{role_type}.pdf"
    tex_filename = f"{today}_{safe_company}_{role_type}.tex"

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
        "tex_filename": tex_filename,
    }
