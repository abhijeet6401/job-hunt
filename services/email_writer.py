"""
Cold email and outreach draft generator using Groq.

Input: company_name, role, contact_name, company_description, observation (optional).
Output: dict with 'draft_1' (direct tone) and 'draft_2' (warmer tone), both plain text.

Saves drafts to Google Sheets Outreach tab.
"""

import logging
from datetime import date

from groq import Groq

from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

USER_CONTEXT = """
You are writing cold outreach emails on behalf of Abhijeet Kumar, an Economics undergraduate at IIT Kharagpur
with strong product management, data analytics, and operational execution experience.

Key facts about Abhijeet:
- Email: kumarabhiitkgp@gmail.com | Phone: +91 63989 85179 | GitHub: github.com/abhijeet6401
- Product and Technology Intern at Aequitas Investment Consultancy ($650M AUM boutique fund):
  * Built unified news & research platform with PERN + TypeScript and MiniLM deduplication, cutting analyst research time by 50%.
  * Developed custom CRM for 1000+ HNI clients, replacing Salesforce and automating lead pipelines.
  * Unified 4+ internal teams and decommissioned 5 legacy tools, boosting client response time by 30%.
- Growth Analytics Intern at Frost & Sullivan:
  * Built predictive time-series models and interactive Power BI dashboards with DAX & SQL for $2.3M+ sales data.
  * Identified 8.0% return rate and demand seasonality across 3 market segments.
- Winner, Product Management (General Championship, IIT Kharagpur):
  * Designed full-stack insurance super-app for 10M+ users, driving INR 120 Cr premium growth with 4 product modules cutting claims cost 35%.
- Runners-up, Indian Case Challenge (ICC Bikaji):
  * Only undergraduate podium finisher among 2000+ global teams; evaluated M&A targets and boosted supply chain efficiency by 15% using ML demand forecasting.
- Research Intern at Felix Advisory & Investment Analyst Intern at India Accelerator:
  * Analyzed $1B+ venture funding patterns and benchmarked $130B addressable market for seed/pre-seed investments.
- Departmental Representative, Career Development Centre (CDC), IIT Kharagpur:
  * Core team of 56 managing campus placements and recruiter relations for 6000+ students.
- Targeting: Product Manager / APM, Founder's Office / Chief of Staff, Data Analyst, and Operations roles.

Email rules:
- Maximum 150 words. Hard limit.
- Lead with a specific, non-generic observation about their product, growth, or company.
- Connect that observation to exactly one relevant thing Abhijeet has done.
- End with one clear ask (a 20-minute call, or a response if they're hiring).
- Never use phrases like: "I am passionate about", "I am excited to", "I would love to",
  "I believe I would be a great fit", "Please find attached", or any generic opener.
- Sound like a smart, proactive IITian builder who understands business metrics and technology, not like a generic cover letter.
"""


def write_emails(
    company_name: str,
    role: str,
    contact_name: str,
    company_description: str,
    observation: str,
    groq_api_key: str,
) -> dict:
    """
    Generate two cold email drafts for a target company/role.

    Draft 1: Direct, no warmth, gets to the point in 2-3 sentences.
    Draft 2: Slightly warmer opener, same structure but less terse.

    Logs both drafts to Google Sheets Outreach tab.
    """
    groq_client = Groq(api_key=groq_api_key)

    contact_line = f"addressed to {contact_name}" if contact_name else "with no specific recipient name"
    observation_line = f"Specific observation to reference: {observation}" if observation else ""

    prompt = f"""
{USER_CONTEXT}

Write TWO cold outreach emails for this situation:
- Company: {company_name}
- Role being applied for: {role}
- Email {contact_line}
- Company description: {company_description}
{observation_line}

Draft 1: Direct and terse. Gets to the point immediately. Professional but not cold.
Draft 2: Slightly warmer. Same structure, but the opener has one more human touch.

Both drafts must be under 150 words. Both must follow all rules above.

Return a JSON object with exactly these two keys:
- "draft_1": string (the direct version)
- "draft_2": string (the warmer version)

No other text. Only valid JSON.
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()

    import json
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        draft_1 = parsed.get("draft_1", "")
        draft_2 = parsed.get("draft_2", "")
    except Exception as e:
        logger.error(f"Failed to parse email drafts: {e}")
        draft_1 = raw
        draft_2 = ""

    today = str(date.today())
    try:
        append_row("Outreach", [
            today,              # Date
            company_name,       # Company
            contact_name or "", # Contact Name
            role,               # Contact Role (using the applied-for role as proxy)
            draft_1,            # Email Draft 1
            draft_2,            # Email Draft 2
            "No",               # Sent
            "No",               # Reply Received
            "",                 # Notes
            "Draft",            # Status
        ])
    except Exception as e:
        logger.warning(f"Failed to log outreach to Sheets: {e}")

    return {
        "draft_1": draft_1,
        "draft_2": draft_2,
        "company": company_name,
        "role": role,
    }
