"""
Form question answer generator using Groq.

Input: question (string), context about the specific role/company (optional string).
Output: dict with 'answer' (plain text, ready to paste) and 'word_count'.

Answers are specific, reference real projects and real metrics, and avoid generic filler phrases.
"""

import logging
from datetime import date

from groq import Groq

from services.sheets import append_row

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

USER_BACKGROUND = """
You are answering application form questions on behalf of Abhijeet Kumar.

Full background:
- Economics undergraduate at IIT Kharagpur (Class of 2027), CGPA 8.03/10, Minor in Mathematics & Computing, Micro-Specialization in AI & Applications.
- Email: kumarabhiitkgp@gmail.com | Phone: +91 63989 85179 | LinkedIn: linkedin.com/in/abhijeetkgp | GitHub: github.com/abhijeet6401
- Honors: UN Millennium Fellow (selected among 5k students globally for UN SDG leadership), NTSE Scholar (State Rank 14), KVPY SA AIR 1487.
- Snabbit (Product Management & Business Strategy Intern, Bengaluru):
  * Scaled retention GOV from 20% to 50% via Blush Prive retention pass; launched manicure & pedicure lifting AOV 2x to Rs 2,000.
  * Saved Rs 50L/month by renegotiating vendor pricing (product cost 40% to 20% of GOV); negotiated Rs 2Cr production order.
  * Managed 100+ SKUs & Rs 30L working capital cutting stock-outs 70%, sustaining 99% fulfillment across 250 daily orders.
- Aequitas Investments (AI Product Management & Finance Strategy Intern, $1Bn AUM fund):
  * Built PERN + TypeScript news deduplication platform cutting research time by 50%.
  * Deployed custom CRM managing 1000+ HNI clients, replacing Salesforce and cutting response time by 30%.
- 3one4 Capital (Portfolio Management & Strategy Intern, Bengaluru):
  * Formulated venture debt, NCDs, and RBF playbooks (9-22% cost) and bridge loan briefs extending runway up to 6 months for portfolio founders.
  * Advised 3 consumer & fintech startups (Seed-IPO) on unit economics, LTV/CAC, and growth patterns.
- Felix Advisory (Research Intern, Gurgaon) & India Accelerator (Investment Analyst Intern, Gurgaon):
  * Drafted 3 investment reports analyzing $1B+ venture funding patterns across Smart Manufacturing, Fintech, and Sports Tech.
  * Benchmarked 15+ competitors mapping $130B market in refurbished tech and evaluated early-stage startups on TAM/SAM/SOM.
- Frost & Sullivan (Business Analytics Intern, Mumbai):
  * Executed predictive time-series models (Moving Averages, Exponential Smoothing) on $23M+ sales data in Power BI with DAX & SQL.
- JobHunt Agent (AI Automation Self-Project):
  * Built full-stack AI job discovery & application assistant aggregating 100+ live listings via Tavily API and xAI LLM.
- Competitions & Leadership:
  * Winner, Product Management (General Championship IIT Kharagpur): Designed insurance super-app for 10M+ users & Rs 120 Cr premium growth.
  * Bronze, Data Analytics (FRAMMER AI General Championship): Built LangGraph multi-agent analytics platform with self-healing SQL pipeline.
  * Runners-up, Indian Case Challenge (ICC Bikaji): Ranked 2nd globally among 2000+ teams in M&A case ($156 Cr valuation).
  * Career Development Centre (CDC) Departmental Representative: Core team of 56 managing campus placements for 6000+ students.
- Skills: Product Management, Data Analytics, Python, SQL, Power BI, DAX, React, TypeScript, Financial Modeling, DCF, Econometrics.
- Targeting: Product Manager / APM, Founder's Office / Chief of Staff, Venture Capital / Strategy, Data Analyst roles.

Writing rules:
1. Under 250 words unless the question clearly demands more.
2. Never use: "I am passionate about", "I am excited to", "I would love to", "I believe",
   "I am a quick learner", "team player", "go-getter", "hard worker", or any generic opener.
3. Lead with a specific fact, decision, or result — never a general statement about yourself.
4. Reference real projects and roles by name (Snabbit, Aequitas, 3one4 Capital, General Championship, CDC) with real metrics.
5. Write in first person, direct voice. Not a cover letter, not an essay. A clear, specific answer.
6. If the question is about motivation or why, answer with a specific decision or moment, not a feeling.
7. If the question is behavioral (tell me about a time...), give one tight story: situation, what you did, result.
"""


def generate_form_answer(
    question: str,
    role_context: str,
    groq_api_key: str,
    company_name: str = "",
) -> dict:
    """
    Generate a focused, specific answer to an application form question.

    Uses full background context about Abhijeet. Respects word limits and avoids generic phrasing.
    Returns the answer as plain text ready to copy-paste, plus word count.
    """
    groq_client = Groq(api_key=groq_api_key)

    context_line = f"\nContext about this specific role/company: {role_context}" if role_context else ""

    prompt = f"""
{USER_BACKGROUND}

{context_line}

Answer this application form question as Abhijeet:

Question: {question}

Return only the answer text. No preamble, no "Here is the answer:", no markdown.
Just the answer, ready to paste into a form.
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.4,
    )

    answer = response.choices[0].message.content.strip()
    word_count = len(answer.split())

    try:
        append_row("Form Answers", [
            str(date.today()),  # Date
            company_name,       # Company
            question,           # Question
            answer,             # Generated Answer
            word_count,         # Word Count
            "No",               # Used (user updates manually)
        ])
    except Exception as e:
        logger.warning(f"Failed to log form answer to Sheets: {e}")

    return {
        "answer": answer,
        "word_count": word_count,
        "question": question,
    }
