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
You are writing cold outreach emails on behalf of Abhijeet Kumar, an Economics undergraduate at IIT Kharagpur (Minor in Maths & Computing, Micro-Spl in AI, CGPA: 8.03/10)
with proven track records across product management, startup strategy, venture capital, and data analytics.

Key facts about Abhijeet:
- Contact: kumarabhiitkgp@gmail.com | +91 63989 85179 | linkedin.com/in/abhijeetkgp | github.com/abhijeet6401
- UN Millennium Fellow: Selected as one of 5,000 students globally for community social impact and leadership aligned with UN SDGs.
- Snabbit (Product Management & Business Strategy Intern, Bengaluru):
  * Scaled retention GOV from 20% to 50% via Blush Prive in-app membership pass; launched manicure & pedicure lifting AOV 2x to Rs 2,000.
  * Saved Rs 50L/month by renegotiating vendor pricing (cutting product cost from 40% to 20% of GOV); negotiated Rs 2Cr production order.
  * Managed 100+ SKUs & Rs 30L working capital cutting stock-outs 70%, sustaining 99% fulfillment across 250 daily orders.
- Aequitas Investments (AI Product Management & Finance Strategy Intern, $1Bn AUM fund):
  * Cut analyst research time by 50% unifying 10+ news sources into a PERN + TypeScript research platform with MiniLM deduplication.
  * Replaced Salesforce with custom CRM serving 1,000+ HNI clients, automating lead tracking and cutting response time by 30%.
- 3one4 Capital (Portfolio Management and Strategy Intern, Bengaluru):
  * Developed venture debt / NCDs / RBF financing playbooks (9-22% cost) and bridge loan briefs helping founders extend runway up to 6 months.
  * Supported 3 consumer & fintech startups (Seed-IPO) ex-CheQ on unit economics, LTV/CAC, and growth patterns.
- Felix Advisory (Research Intern, Gurgaon):
  * Drafted 3 investment reports analyzing $1B+ funding patterns across Smart Manufacturing, Fintech, and Sports Tech; mapped 6+ whitespace areas.
- India Accelerator (Investment Analyst Intern, Gurgaon):
  * Evaluated early-stage startups using TAM/SAM/SOM and unit economics; benchmarked 15+ competitors mapping $130B market in refurbished tech.
- JobHunt Agent (AI Automation Self-Project):
  * Built full-stack AI job discovery & tailoring assistant aggregating 100+ live listings via Tavily API and xAI LLM on FastAPI & Render.
- Competitions & Leadership:
  * Winner, Product Management (General Championship IIT Kharagpur): Designed insurance super-app for 10M+ users & Rs 120 Cr premium growth.
  * Bronze, Data Analytics (FRAMMER AI General Championship): Built LangGraph multi-agent analytics platform with self-healing SQL pipeline.
  * Runners-up, Indian Case Challenge (ICC Bikaji): Ranked 2nd globally among 2000+ teams in M&A case ($156 Cr valuation).
  * Career Development Centre (CDC) Departmental Representative: Core team of 56 managing campus placements for 6000+ students.
- Targeting: Product Manager / APM, Founder's Office / Chief of Staff, Venture Capital / Strategy, Data & Business Analyst roles.

Email rules:
- Maximum 150 words. Hard limit.
- Lead with a specific, non-generic observation about their product, growth, or company.
- Connect that observation to exactly one relevant thing Abhijeet has done.
- End with one clear ask (a 20-minute call, or a response if they're hiring).
- Never use phrases like: "I am passionate about", "I am excited to", "I would love to",
  "I believe I would be a great fit", "Please find attached", or any generic opener.
- Sound like a smart, proactive builder who understands metrics, technology, and business growth.
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
