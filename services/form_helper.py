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
- Economics undergraduate at IIT Kharagpur (Class of 2027), CGPA 7.82/10.
- Email: kumarabhiitkgp@gmail.com | Phone: +91 63989 85179 | GitHub: github.com/abhijeet6401
- Product & Technology Intern at Aequitas Investment Consultancy ($650M AUM boutique fund):
  * Built unified research platform using PERN + TypeScript and MiniLM deduplication, cutting analyst research time by 50%.
  * Deployed custom CRM to manage 1000+ HNI clients, replacing Salesforce and automating lead tracking.
  * Unified 4+ internal teams, replaced 5 legacy tools, cutting client response time by 30%.
- Growth Analytics Intern at Frost & Sullivan:
  * Executed predictive time series modeling (Moving Averages, Exponential Smoothing) on $2.3M+ multi-country sales data.
  * Deployed interactive Power BI dashboards with DAX and SQL; diagnosed 8.0% return rate and demand seasonality.
- Winner, Product Management (General Championship IIT Kharagpur):
  * Designed end-to-end insurance super-app for 10M+ users, driving INR 120 Cr premium growth with 4 product modules cutting claims cost 35%.
- Runners-up, Indian Case Challenge (ICC Bikaji):
  * Top undergraduate team among 2000+ global entries; evaluated Loyka acquisition at INR 156 Cr (28% IRR) and improved supply chain efficiency by 15% via ML demand forecasting.
- Research Intern at Felix Advisory & Investment Analyst Intern at India Accelerator:
  * Analyzed $1B+ funding patterns and benchmarked $130B addressable market for seed/pre-seed startups.
- Departmental Representative, Career Development Centre (CDC) IIT Kharagpur:
  * Facilitating campus placements and internships for 6000+ students, coordinating hiring operations with 100+ top recruiters.
- Skills: Product Management, Data Analytics, Python, SQL, Power BI, DAX, React, TypeScript, Financial Modeling, DCF, Econometrics.
- Targeting: Product Manager / APM, Founder's Office / Chief of Staff, Data Analyst, Operations roles.

Writing rules:
1. Under 250 words unless the question clearly demands more.
2. Never use: "I am passionate about", "I am excited to", "I would love to", "I believe",
   "I am a quick learner", "team player", "go-getter", "hard worker", or any generic opener.
3. Lead with a specific fact, decision, or result — never a general statement about yourself.
4. Reference real projects and roles by name (Aequitas, Frost & Sullivan, General Championship, CDC) with real metrics.
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
