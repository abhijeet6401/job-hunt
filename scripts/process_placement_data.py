#!/usr/bin/env python3
"""
IIT Kharagpur Placement Central Repository & Analytics Processor.

Processes CDC Placement datasets across multiple seasons (2024-25, 2023-24, etc.)
into normalized, structured JSON repositories with CTC intelligence, canonical
company matching, job description extraction, and senior outreach helpers.
"""

import csv
import glob
import json
import os
import re
import urllib.parse
from collections import Counter, defaultdict
from typing import Dict, Any, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

COMPANY_CANONICAL_MAP = {
    # HFT / Quant / Trading
    "OPTIVER": "Optiver",
    "Optiver": "Optiver",
    "QUADEYE": "Quadeye Securities",
    "Quadeye": "Quadeye Securities",
    "Quadeye Securities": "Quadeye Securities",
    "GRAVITON RESEARCH CAPITAL LLP": "Graviton Research Capital",
    "Graviton Research Capital": "Graviton Research Capital",
    "ALPHAGREP": "AlphaGrep",
    "AlphaGrep": "AlphaGrep",
    "QUANTBOX RESEARCH": "Quantbox Research",
    "Quantbox Research": "Quantbox Research",
    "NK Securities Research": "NK Securities Research",
    "NK Securities": "NK Securities Research",
    "TREXQUANT": "Trexquant",
    "Trexquant": "Trexquant",
    "SQUAREPOINT CAPITAL": "Squarepoint Capital",
    "Squarepoint Capital": "Squarepoint Capital",
    "Edelweiss Global Markets": "Edelweiss Global Markets",
    "Plutus Research Pvt Ltd": "Plutus Research",
    "Plutus Research": "Plutus Research",
    "AXXELA": "Axxela Research & Analytics",
    "Axxela Research & Analytics Private Limited": "Axxela Research & Analytics",
    "Futures First": "Futures First",
    "FUTURES FIRST": "Futures First",

    # Tech Giants & Top Product Companies
    "GOOGLE": "Google",
    "Google": "Google",
    "MICROSOFT": "Microsoft",
    "Microsoft": "Microsoft",
    "AMAZON": "Amazon",
    "Amazon": "Amazon",
    "APPLE": "Apple",
    "Apple": "Apple",
    "DATABRICKS": "Databricks",
    "Databricks": "Databricks",
    "NVIDIA": "Nvidia",
    "Nvidia Graphics Limited": "Nvidia",
    "Nvidia": "Nvidia",
    "QUALCOMM": "Qualcomm",
    "Qualcomm": "Qualcomm",
    "QUALCOMM INDIA PVT LTD": "Qualcomm",
    "Qualcomm India Pvt Ltd": "Qualcomm",
    "TEXAS INSTRUMENTS": "Texas Instruments",
    "TEXAS INSTRUMENTS, BANGALORE": "Texas Instruments",
    "Texas Instruments": "Texas Instruments",
    "ORACLE": "Oracle",
    "Oracle": "Oracle",
    "SALESFORCE": "Salesforce",
    "UBER": "Uber",
    "Uber": "Uber",
    "NUTANIX": "Nutanix",
    "Nutanix": "Nutanix",
    "GLEAN": "Glean",
    "Glean Search Technologies India Pvt. Ltd": "Glean",
    "RIPPLING": "Rippling",
    "Rippling": "Rippling",
    "SPRINKLR": "Sprinklr",
    "Sprinklr": "Sprinklr",
    "COHESITY": "Cohesity",
    "DEVREV": "DevRev",
    "RUBRIK": "Rubrik",
    "RUBRIK INDIA": "Rubrik",
    "Rubrik": "Rubrik",
    "CISCO": "Cisco",
    "INTUIT": "Intuit",
    "ADOBE": "Adobe",
    "ADOBE RESEARCH": "Adobe",
    "Adobe": "Adobe",
    "ENPHASE ENERGY": "Enphase Energy",
    "ENPHASE ENERGY PVT. LTD.": "Enphase Energy",
    "Enphase Energy Pvt. Ltd.": "Enphase Energy",
    "HONEYWELL": "Honeywell",
    "Honeywell": "Honeywell",
    "IBM": "IBM",
    "IBM India": "IBM",
    "KLA": "KLA",
    "MICRON": "Micron",
    "POSTMAN": "Postman",
    "Postman": "Postman",
    "UIPATH": "UiPath",
    "COINBASE": "Coinbase",
    "HARNESS": "Harness",
    "Harness": "Harness",
    "THOUGHTSPOT": "ThoughtSpot",
    "SIEMENS EDA": "Siemens EDA",
    "SIEMENS EDA (INDIA) PRIVATE LIMITED": "Siemens EDA",
    "Siemens EDA (_India_) Private Limited": "Siemens EDA",
    "Siemens EDA (Mentor Graphics)": "Siemens EDA",
    "MENTOR GRAPHICS - A SIEMENS BUSINESS": "Siemens EDA",
    "MathWorks India Private Limited": "MathWorks",
    "MathWorks": "MathWorks",
    "MATHWORKS": "MathWorks",
    "MEDATEK": "MediaTek",
    "MEDIATEK": "MediaTek",
    "Mediatek Bangalore Private Limited": "MediaTek",
    "ANALOG DEVICES INDIA": "Analog Devices",
    "LAM RESEARCH": "Lam Research",
    "APPLIED MATERIALS": "Applied Materials",
    "Applied Materials": "Applied Materials",
    "Intel India Ltd.": "Intel",
    "Intel India Ltd": "Intel",
    "INTEL": "Intel",
    "APPLE INDIA PRIVATE LIMITED": "Apple",
    "GOOGLE INDIA PVT LTD": "Google",
    "QUANTBOX": "Quantbox Research",
    "Quantbox Research": "Quantbox Research",
    "Rakuten Group, Inc.": "Rakuten",
    "Rakuten Mobile, Inc.": "Rakuten",
    "Rakuten": "Rakuten",
    "D. E. SHAW": "D. E. Shaw",
    "D. E. Shaw": "D. E. Shaw",
    "D.E. SHAW AND CO": "D. E. Shaw",
    "D.E. Shaw": "D. E. Shaw",
    "D. E. Shaw India": "D. E. Shaw",

    # Samsung
    "SRI B": "Samsung Research (SRI-Bangalore)",
    "Samsung Research Bangalore": "Samsung Research (SRI-Bangalore)",
    "SAMSUNG RESEARCH, BENGALURU": "Samsung Research (SRI-Bangalore)",
    "SAMSUNG RESEARCH INSTITUTE BANGLORE": "Samsung Research (SRI-Bangalore)",
    "SAMSUNG R&D INSTITUTE - BANGLORE": "Samsung Research (SRI-Bangalore)",
    "SRI N": "Samsung Research (SRI-Delhi)",
    "SRI DELHI": "Samsung Research (SRI-Delhi)",
    "SRI - DELHI": "Samsung Research (SRI-Delhi)",
    "SRI -DEHLI": "Samsung Research (SRI-Delhi)",
    "SAMSUNG RESEARCH INSTITUTE, DELHI.": "Samsung Research (SRI-Delhi)",
    "SAMSUNG R&D INSTITUTE - DELHI": "Samsung Research (SRI-Delhi)",
    "Samsung Research and Development Institute India Delhi": "Samsung Research (SRI-Delhi)",
    "SAMSUNG R&D INSTITUTE - NOIDA": "Samsung R&D (Noida)",
    "SAMSUNG SEMICONDUCTORS": "Samsung Semiconductors",
    "SAMSUNG": "Samsung",

    # Finance / Investment Banking / Fintech
    "GOLDMAN SACHS": "Goldman Sachs",
    "Goldman Sachs": "Goldman Sachs",
    "JPMORGAN CHASE AND CO.": "JPMorgan Chase & Co.",
    "JPMorganChase": "JPMorgan Chase & Co.",
    "JPMorgan Chase": "JPMorgan Chase & Co.",
    "MORGAN STANLEY": "Morgan Stanley",
    "Morgan Stanley": "Morgan Stanley",
    "NOMURA": "Nomura",
    "Nomura": "Nomura",
    "BLACKROCK": "BlackRock",
    "BlackRock": "BlackRock",
    "AMERICAN EXPRESS": "American Express",
    "American Express": "American Express",
    "MASTERCARD": "Mastercard",
    "Mastercard": "Mastercard",
    "VISA": "Visa",
    "Visa Inc": "Visa",
    "Visa": "Visa",
    "WELLS FARGO": "Wells Fargo",
    "Wells Fargo": "Wells Fargo",
    "CITI BANK": "Citi",
    "Citi Bank": "Citi",
    "CITI": "Citi",
    "BNY MELLON": "BNY Mellon",
    "BANK OF AMERICA": "Bank of America",
    "BARCLAYS": "Barclays",
    "Barclays": "Barclays",
    "CAPITAL ONE": "Capital One",
    "Capital One": "Capital One",
    "CRED": "CRED",
    "NAVI": "Navi",
    "Navi": "Navi",
    "NAVI TECHNOLOGIES": "Navi",
    "Navi Technologies Pvt. Ltd.": "Navi",
    "CASHFREE PAYMENTS": "Cashfree Payments",
    "Cashfree Payments": "Cashfree Payments",
    "PIRAMAL FINANCE": "Piramal Finance",
    "PIRAMAL CAPITAL AND HOUSING FINANCE": "Piramal Finance",
    "Piramal Finance Limited": "Piramal Finance",
    "STANDARD CHARTERED": "Standard Chartered",
    "Standard Chartered GBS Pvt Ltd": "Standard Chartered",
    "STANDARD CHARTERED GBS PVT LTD": "Standard Chartered",
    "Standard Chartered": "Standard Chartered",
    "AXIS BANK": "Axis Bank",
    "Axis Bank": "Axis Bank",
    "ICICI Bank Ltd.": "ICICI Bank",
    "ICICI Bank": "ICICI Bank",
    "ICICI Securities": "ICICI Securities",
    "IDFC FIRST Bank": "IDFC FIRST Bank",
    "IDFC First Bank": "IDFC FIRST Bank",
    "BANDHAN BANK": "Bandhan Bank",
    "Bandhan Bank": "Bandhan Bank",
    "FIDELITY INVESTMENTS": "Fidelity Investments",
    "NPCI": "NPCI",
    "TATA AIG": "Tata AIG",
    "TATA AIG GENERAL INSURANCE COMPANY LIMITED": "Tata AIG",
    "Dezerv Investments Pvt. Ltd.": "Dezerv",
    "Arpwood Capital": "Arpwood Capital",
    "FinBox": "FinBox",
    "Natwest Group": "Natwest Group",

    # Consulting & Strategy
    "BCG": "Boston Consulting Group (BCG)",
    "BOSTON CONSULTING GROUP": "Boston Consulting Group (BCG)",
    "Boston Consulting Group": "Boston Consulting Group (BCG)",
    "BAIN AND COMPANY": "Bain & Company",
    "Bain & Company": "Bain & Company",
    "MCKINSEY & COMPANY": "McKinsey & Company",
    "McKinsey & Company": "McKinsey & Company",
    "L.E.K. CONSULTING": "L.E.K. Consulting",
    "ACCENTURE": "Accenture",
    "Accenture": "Accenture",
    "ACCENTURE OPERATIONS": "Accenture",
    "Accenture Strategy and Consulting": "Accenture",
    "Accenture Japan Ltd.": "Accenture",
    "Accenture Strategy and Consulting - Applied Intelligence": "Accenture",
    "DELOITTE TOUCHE TOHMATSU INDIA LLP": "Deloitte",
    "Deloitte US India": "Deloitte",
    "Deloitte": "Deloitte",
    "PwC AC": "PwC",
    "PwC": "PwC",
    "PwC India": "PwC",
    "EY Global Delivery Services India LLP": "EY (Ernst & Young)",
    "EY Parthenon": "EY-Parthenon",
    "EY": "EY (Ernst & Young)",
    "EY-INDIA": "EY (Ernst & Young)",
    "EY GDS": "EY (Ernst & Young)",
    "AURONOVA CONSULTING": "Auronova Consulting",
    "Indus Insights": "Indus Insights",
    "Kepler Cannon": "Kepler Cannon",
    "KEPLER CANNON": "Kepler Cannon",
    "YCP Auctus": "YCP Auctus",

    # Startups / E-Commerce
    "MEESHO": "Meesho",
    "Meesho Limited": "Meesho",
    "Meesho": "Meesho",
    "ZEPTO": "Zepto",
    "Zepto": "Zepto",
    "SWIGGY": "Swiggy",
    "Swiggy": "Swiggy",
    "FLIPKART": "Flipkart",
    "Flipkart Internet Private Limited": "Flipkart",
    "Flipkart": "Flipkart",
    "BLINKIT": "Blinkit",
    "Blinkit": "Blinkit",
    "OLA": "Ola",
    "Ola": "Ola",
    "OLA ELECTRIC": "Ola Electric",
    "URBAN COMPANY": "Urban Company",
    "Urban Company": "Urban Company",
    "UNIFYAPPS": "UnifyApps",
    "WALMART": "Walmart Global Tech",
    "WALMART GLOBAL TECH": "Walmart Global Tech",
    "WALMART GLOBAL TECH INDIA": "Walmart Global Tech",
    "NoBroker Technologies Solutions Pvt LTD": "NoBroker",
    "NOBROKER TECHNOLOGIES SOLUTIONS PVT LTD": "NoBroker",
    "NO BROKER TECHNOLOGIES PVT LTD": "NoBroker",
    "NoBroker": "NoBroker",
    "NxtWave Disruptive Technologies Private Limited": "NxtWave",
    "Ather Energy": "Ather Energy",
    "PATTERN": "Pattern",
    "INITO": "Inito",
    "EBAY": "eBay",
    "eBay": "eBay",
    "ETERNAL": "Eternal",
    "MONEYVIEW": "Moneyview",
    "Mygate": "Mygate",
    "Landeed (John Salt Pvt Limited)": "Landeed",
    "CARS24": "Cars24",
    "SuperAGI": "SuperAGI",
    "WINZO": "WinZO",
    "Battery Smart": "Battery Smart",
    "BATTERY SMART": "Battery Smart",
    "DoubleTick | QuickSell": "DoubleTick",
    "Signzy": "Signzy",

    # Analytics / AI / Specialized
    "EXL Service": "EXL Service",
    "EXL": "EXL Service",
    "AXTRIA": "Axtria",
    "Axtria India Pvt Ltd": "Axtria",
    "Axtria": "Axtria",
    "TCG DIGITAL": "TCG Digital",
    "TCG Digital Solutions Pvt Ltd": "TCG Digital",
    "HILABS": "HiLabs",
    "HiLabs": "HiLabs",
    "Fractal Analytics": "Fractal Analytics",
    "Quantiphi Analytics": "Quantiphi",
    "Straive": "Straive",
    "Aviso Software India LLP (Aviso AI)": "Aviso AI",
    "AVISO AI": "Aviso AI",
    "FN MATHLOGIC": "FN MathLogic",
    "Insurity Solutions India Private Limited": "Insurity Solutions",
    "Telus Digital": "Telus Digital",
    "Samsara": "Samsara",
    "GigaML": "GigaML",
    "Penguin Ai": "Penguin AI",

    # Core Engineering, Aerospace, Auto, Energy & Manufacturing
    "AIRBUS": "Airbus",
    "Airbus India Private Limited": "Airbus",
    "Airbus": "Airbus",
    "CATERPILLAR": "Caterpillar",
    "Skyroot Aerospace": "Skyroot Aerospace",
    "BOEING": "Boeing",
    "Tesla": "Tesla",
    "BAJAJ": "Bajaj Auto",
    "Bajaj Auto Ltd. and Bajaj Auto Technology Ltd.": "Bajaj Auto",
    "Bajaj Auto Limited": "Bajaj Auto",
    "BAJAJ AUTO": "Bajaj Auto",
    "JLR TBSI": "Jaguar Land Rover (JLR)",
    "JLR": "Jaguar Land Rover (JLR)",
    "JAGUAR LAND ROVER": "Jaguar Land Rover (JLR)",
    "JAGUAR LAND ROVER INDIA LIMITED": "Jaguar Land Rover (JLR)",
    "TVS MOTOR COMPANY": "TVS Motor Company",
    "TVSM": "TVS Motor Company",
    "TVS Motor company limited": "TVS Motor Company",
    "TATA STEEL": "Tata Steel",
    "TATA PROJECTS LIMITED": "Tata Projects",
    "TATA Projects Limited": "Tata Projects",
    "Tata Projects": "Tata Projects",
    "JOHN DEERE": "John Deere",
    "John Deere Pvt Ltd": "John Deere",
    "John Deere": "John Deere",
    "VEDANTA": "Vedanta",
    "VEDANTA LIMITED": "Vedanta",
    "Vedanta Limited": "Vedanta",
    "Larsen and Toubro Limited": "Larsen & Toubro (L&T)",
    "LARSEN & TOUBRO": "Larsen & Toubro (L&T)",
    "L&T Finance": "L&T Finance",
    "ITC LIMITED": "ITC Limited",
    "ITC Limited": "ITC Limited",
    "ITC": "ITC Limited",
    "SLB": "SLB (Schlumberger)",
    "Schlumberger": "SLB (Schlumberger)",
    "CAIRN": "Cairn Oil & Gas (Vedanta)",
    "Cairn India (Oil & Gas)": "Cairn Oil & Gas (Vedanta)",
    "Cairn Oil & Gas  Vedanta Limited": "Cairn Oil & Gas (Vedanta)",
    "CAIRN OIL AND GAS": "Cairn Oil & Gas (Vedanta)",
    "ExxonMobil Services & Technology Private Limited": "ExxonMobil",
    "EXXON MOBIL": "ExxonMobil",
    "EXXONMOBIL INDIA": "ExxonMobil",
    "Reliance Industries Limited (New Energy Initiatives)": "Reliance Industries (New Energy)",
    "Reliance Industries Ltd": "Reliance Industries",
    "RELIANCE": "Reliance Industries",
    "Reliance Jio Infocomm": "Reliance Jio",
    "Reliance Jio 5G": "Reliance Jio",
    "Reliance Jio": "Reliance Jio",
    "Solar Defence & Aerospace Limited": "Solar Defence & Aerospace",
    "Siemens Energy India Limited": "Siemens Energy",
    "Eaton India Innovation Center": "Eaton",
    "EATON": "Eaton",
    "Eaton Technologies": "Eaton",
    "GE Vernova": "GE Vernova",
    "GE Bengaluru": "GE",
    "JSW": "JSW",
    "JSW GROUP": "JSW",
    "GODREJ PROPERTIES": "Godrej Properties",
    "Godrej Properties Limited": "Godrej Properties",
    "Thornton Tomasetti": "Thornton Tomasetti",
    "BECHTEL INDIA PVT LTD": "Bechtel",
    "IHI CORPORATION": "IHI Corporation",
    "DENSO": "DENSO",
    "PROCTOR AND GAMBLE": "Procter & Gamble (P&G)",
    "PANDG": "Procter & Gamble (P&G)",
    "Procter and Gamble": "Procter & Gamble (P&G)",
    "GENERAL MILLS": "General Mills",
    "General Mills": "General Mills",
    "HUL": "Hindustan Unilever (HUL)",
    "HINDUSTAN UNILEVER LTD.": "Hindustan Unilever (HUL)",
    "Hindustan Unilever": "Hindustan Unilever (HUL)",
    "Centre for Development of Telematics": "C-DOT",
    "Rekise Marine Private Limited": "Rekise Marine",
    "Slnko Energy Pvt Ltd": "Slnko Energy",
    "SEDEMAC Mechatronics Limited": "SEDEMAC Mechatronics",
    "Sedemac Mechatronics": "SEDEMAC Mechatronics",
    "SEDEMAC": "SEDEMAC Mechatronics",
    "DTDC": "DTDC Express",
    "DTDC Express Limited": "DTDC Express",
    "FedEx": "FedEx",
    "ONESUBSEA": "OneSubsea",
    "Oceaneering International Services Ltd": "Oceaneering International",
    "BP": "BP (British Petroleum)",
}


def clean_company_name(raw_name: str) -> str:
    """Standardize company name into canonical representation."""
    if not raw_name:
        return "Unknown Company"
    trimmed = raw_name.strip()
    if trimmed in COMPANY_CANONICAL_MAP:
        return COMPANY_CANONICAL_MAP[trimmed]
    for k, v in COMPANY_CANONICAL_MAP.items():
        if k.lower() == trimmed.lower():
            return v
    if trimmed.isupper() and len(trimmed) > 4 and " " in trimmed:
        return " ".join(w.capitalize() for w in trimmed.split())
    return trimmed


def parse_ctc(ctc_raw: str, company_name: str = "", designation: str = "") -> Tuple[Optional[float], str]:
    """Parse CTC string into (ctc_in_lpa, display_string)."""
    if not ctc_raw or not ctc_raw.strip():
        return None, "Not Disclosed"

    s = ctc_raw.strip()

    # Explicit known non-monetary placeholders
    if s.upper() in ["WALKING", "NA", "N/A", "-", "NONE", "UNPLACED", "INTERVIEW"]:
        return None, "Not Disclosed"

    # 1. Google special format (~60LAKHS ...)
    if "~60LAKHS" in s.upper() or "2410000 INR BASE" in s.upper():
        return 60.0, "₹60.00 LPA (₹24.1L Base + ₹3.25L Bonus + Stock)"

    # 2. Salesforce multi-component strings
    if "16.5" in s and ("RSU" in s.upper() or "DOLLARS" in s.upper()):
        return 46.0, "₹46.00 LPA (₹16.5L Base + ₹5L Bonus + $28K RSUs)"

    # 3. DevRev ESOP string
    if "30,00,000" in s and "ESOP" in s.upper():
        return 35.0, "₹30.00 LPA + 3,000 ESOP Units"

    # 4. Skyroot multi-tier table string
    if "Skyroot" in company_name and len(s) > 100:
        return 16.0, "₹16.00 LPA (₹12L Base + Performance + ESOPs)"

    # 5. JPY / YEN handling (e.g. "4100000 YEN", "6825000 YEN", "4000000 JPY", "6300000 JPY")
    if "YEN" in s.upper() or "JPY" in s.upper():
        m = re.search(r"([\d,]+)", s)
        if m:
            yen = float(m.group(1).replace(",", ""))
            # Conversion rate approx 0.55 INR per JPY
            lpa = round((yen * 0.55) / 100000.0, 2)
            yen_in_lakh = round(yen / 100000.0, 1)
            return lpa, f"¥{yen_in_lakh}L (≈ ₹{lpa:.1f} LPA)"

    # 6. USD handling (e.g. "USD 50,000/YEAR...", "48000 USD", "$180000", etc.)
    if "USD" in s.upper() or "$" in s:
        m = re.search(r"(?:USD|\$)\s*([\d,]+)", s, re.IGNORECASE)
        if not m:
            m = re.search(r"([\d,]+)\s*(?:USD|\$)", s, re.IGNORECASE)
        if m:
            usd_str = m.group(1).replace(",", "")
            if usd_str:
                usd = float(usd_str)
                if usd >= 10000:
                    lpa = round((usd * 84.0) / 100000.0, 2)
                    return lpa, f"${usd:,.0f} USD (≈ ₹{lpa:.1f} LPA)"

    if s == "180000" and ("USA" in designation or "RISA" in company_name):
        lpa = round(180000 * 84 / 100000, 2)
        return lpa, f"$180,000 USD (≈ ₹{lpa:.1f} LPA)"

    # 7. Strings with formulas, brackets or breakdowns like:
    # "952576 INR [BASIC PAY + JOINING BONUS/ RETENTION=(852576+ 100000 )]"
    # or "RS.1,350,000 PER ANNUM"
    # Take the leading total monetary figure before bracket or suffix
    leading_match = re.search(r"^(?:RS\.?|INR)?\s*([\d,]+(?:\.\d+)?)", s, re.IGNORECASE)
    if leading_match:
        cand_str = leading_match.group(1).replace(",", "")
        try:
            val = float(cand_str)
            if val > 1000000:
                lpa = round(val / 100000.0, 2)
                if lpa >= 100.0:
                    cr = lpa / 100.0
                    return lpa, f"₹{cr:.2f} Cr ({lpa:.1f} LPA)"
                else:
                    return lpa, f"₹{lpa:.2f} LPA"
            elif val > 50000:
                lpa = round(val / 100000.0, 2)
                return lpa, f"₹{lpa:.2f} LPA"
            elif 0 < val <= 200:
                return round(val, 2), f"₹{val:.2f} LPA"
        except ValueError:
            pass

    clean_num = re.sub(r"[^\d.]", "", s)
    if clean_num:
        try:
            val = float(clean_num)
            if val > 1000000:
                lpa = round(val / 100000.0, 2)
                if lpa >= 100.0:
                    cr = lpa / 100.0
                    return lpa, f"₹{cr:.2f} Cr ({lpa:.1f} LPA)"
                else:
                    return lpa, f"₹{lpa:.2f} LPA"
            elif val > 50000:
                lpa = round(val / 100000.0, 2)
                return lpa, f"₹{lpa:.2f} LPA"
            elif 0 < val <= 200:
                return round(val, 2), f"₹{val:.2f} LPA"
        except ValueError:
            pass

    return None, s


def clean_role_and_jd(designation_raw: str, company: str) -> Tuple[str, str]:
    """Extract clean role title and detailed JD."""
    if not designation_raw:
        return "Not Specified", ""

    text = designation_raw.strip()

    if "Degree Job Title Compensation" in text:
        return "GET / PGET (Aerospace & Core)", text

    if "Role Overview" in text or "We are looking for" in text:
        split_match = re.split(r"Role Overview|We are looking for", text, maxsplit=1)
        role_part = split_match[0].strip()
        jd_part = text
        if not role_part:
            role_part = "Associate Analyst, Advanced Analytics"
        return role_part, jd_part

    if len(text) <= 80:
        return text, ""

    parts = text.split(".", 1)
    role_part = parts[0][:70].strip()
    return role_part, text


def parse_offer_slot(offer_date_raw: str, placement_type: str) -> str:
    """Format offer date into placement slot name (Day 1, Day 2, etc.)."""
    if placement_type == "PPO":
        return "PPO (Pre-Placement Offer)"
    if not offer_date_raw or not offer_date_raw.strip():
        return "Placement Drive"

    d = offer_date_raw.strip()
    if "01-12" in d:
        return "Day 1 (Dec 1)"
    elif "02-12" in d:
        return "Day 1 (Dec 2)"
    elif "03-12" in d:
        return "Day 2 (Dec 3)"
    elif "04-12" in d:
        return "Day 3 (Dec 4)"
    elif "05-12" in d:
        return "Day 4 (Dec 5)"
    elif "06-12" in d or "07-12" in d:
        return "Day 5-6"
    else:
        return f"CDC Drive ({d})"


def generate_outreach_templates(name: str, company: str, role: str, dept: str) -> Tuple[str, str, str]:
    """Generate pre-drafted outreach templates for WhatsApp and Email."""
    first_name = name.split()[0].title() if name else "Senior"
    senior_salutation = f"{first_name} bhaiya/didi"

    wa_msg = (
        f"Hi {senior_salutation}, I am Abhijeet Kumar from IIT Kharagpur ({dept} Dept). "
        f"Heartiest congratulations on your placement at {company} as {role}! "
        f"I will be sitting for the upcoming placement season and am preparing for similar roles. "
        f"Whenever you have 5-10 minutes, could I please ask you a couple of questions about the interview process and preparation tips? "
        f"Your guidance would mean a lot to me. Thank you so much!"
    )

    email_subject = f"[IIT KGP Guidance] Placement Advice for {company} — Abhijeet Kumar ({dept})"
    email_body = (
        f"Dear {first_name},\n\n"
        f"Hope you are having a great week!\n\n"
        f"My name is Abhijeet Kumar, a student at IIT Kharagpur ({dept}). "
        f"Congratulations on getting placed at {company} as {role}!\n\n"
        f"I am preparing for the upcoming CDC placement drive and aiming for opportunities in {company}. "
        f"I would be deeply grateful if you could spare 10 minutes over call or email to share any insights on:\n"
        f"1. Key focus areas for the Online Assessment (OA) and technical rounds\n"
        f"2. Important projects or skills that helped you stand out\n"
        f"3. Any pitfalls or advice you wish someone told you before placements\n\n"
        f"Thank you for your time and guidance!\n\n"
        f"Warm regards,\n"
        f"Abhijeet Kumar\n"
        f"IIT Kharagpur\n"
        f"abhijeetkumar@kgpian.iitkgp.ac.in"
    )

    return wa_msg, email_subject, email_body


def get_dataset_files() -> List[Tuple[str, str]]:
    """
    Return list of (filepath, season_name) for all placement CSVs in data directory.
    Sorted in descending chronological order (latest season first).
    """
    files = []
    # Primary known seasons
    known_seasons = [
        ("cdc_placements_2025_2026.csv", "2025-26"),
        ("cdc_placements_2023_2024.csv", "2023-24"),
        ("cdc_placements_2022_2023.csv", "2022-23"),
        ("cdc_placements_2021_2022.csv", "2021-22"),
    ]
    for fname, s_name in known_seasons:
        p = os.path.join(DATA_DIR, fname)
        if os.path.exists(p):
            files.append((p, s_name))

    # Any additional uploaded CSVs in data folder
    for p in glob.glob(os.path.join(DATA_DIR, "*.csv")):
        basename = os.path.basename(p)
        if basename in ["cdc_placements_2025_2026.csv", "cdc_placements_2024_2025.csv", "cdc_placements_2023_2024.csv", "cdc_placements_2022_2023.csv", "cdc_placements_2021_2022.csv", "cdc_placements_raw.csv"]:
            continue
        if "placement" in basename.lower() or "upload" in basename.lower():
            m = re.search(r"(\d{2,4})[_-](\d{2,4})", basename)
            if m:
                y1 = m.group(1)[-2:]
                y2 = m.group(2)[-2:]
                s_name = f"20{y1}-{y2}"
            else:
                s_name = basename.replace(".csv", "")
            if not any(f[1] == s_name for f in files):
                files.append((p, s_name))

    return files


def process_all_placement_data():
    """
    Read all placement CSVs, merge them with season tags, and output JSON repositories.
    """
    files = get_dataset_files()
    print(f"Found {len(files)} placement CSV datasets to ingest: {[f[1] for f in files]}")

    all_candidates = []
    placed_students = []
    companies_dict = defaultdict(lambda: {
        "raw_names": set(),
        "students": [],
        "sectors": set(),
        "company_categories": set(),
        "departments": Counter(),
        "degrees": Counter(),
        "designations": Counter(),
        "ctc_list": [],
        "cgpa_list": [],
        "offer_dates": Counter(),
        "jds": set(),
        "ppo_count": 0,
        "non_ppo_count": 0,
        "seasons": Counter(),
    })

    dept_counter = Counter()
    sector_counter = Counter()
    degree_counter = Counter()
    placement_type_counter = Counter()
    season_counter = Counter()

    candidate_id = 0
    seen_candidates_season = set()

    for csv_path, season_label in files:
        if not os.path.exists(csv_path):
            continue

        print(f"Processing season [{season_label}]: {csv_path}")
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        if len(all_lines) < 3:
            continue

        # Skip header metadata rows if needed
        data_lines = all_lines
        if "All Registered Candidates" in all_lines[0]:
            data_lines = all_lines[2:]
        elif "#,Type" in all_lines[1]:
            data_lines = all_lines[1:]

        reader = csv.DictReader(data_lines)

        for r in reader:
            rollno = r.get("Rollno", "").strip()
            if rollno and (rollno, season_label) in seen_candidates_season:
                continue
            if rollno:
                seen_candidates_season.add((rollno, season_label))

            candidate_id += 1
            name = r.get("Name", "").strip()
            rollno = r.get("Rollno", "").strip()
            dept = r.get("Dept", "").strip()
            dept_name = r.get("Dept Name", "").strip()
            degree = r.get("Degree", "").strip()
            course_name = r.get("Course Name", "").strip()
            category = r.get("Category", "").strip()
            email = r.get("Email", "").strip()
            phone = r.get("Phone", "").strip()
            placed_in_raw = r.get("Placed in", "").strip()
            company_cat = r.get("Category of company", "").strip()
            sector = r.get("Sector", "").strip()
            placement_type = r.get("Type of Placement", "").strip() or ("PPO" if "PPO" in r.get("Designation", "") else "NON-PPO")
            designation_raw = r.get("Designation", "").strip()
            ctc_raw = r.get("CTC/Stipend", "").strip()
            offer_date = r.get("Offer Date", "").strip()
            minor = r.get("Minor", "").strip()
            micro = r.get("Micro", "").strip()
            dob = r.get("DOB", "").strip()
            gender = r.get("Gender", "").strip()

            cgpa_str = r.get("CGPA", "").strip()
            cgpa_val = None
            if cgpa_str and cgpa_str != "-":
                try:
                    cgpa_val = float(cgpa_str)
                except ValueError:
                    cgpa_val = None

            is_placed = bool(placed_in_raw)

            candidate_record = {
                "id": candidate_id,
                "season": season_label,
                "name": name.title() if name else f"Student ({rollno})",
                "rollno": rollno,
                "dept": dept,
                "dept_name": dept_name,
                "degree": degree,
                "course_name": course_name,
                "category": category,
                "email": email,
                "phone": phone,
                "is_placed": is_placed,
                "cgpa": cgpa_val,
                "minor": minor,
                "micro": micro,
                "dob": dob,
                "gender": gender,
            }

            if is_placed:
                company_canon = clean_company_name(placed_in_raw)
                clean_role, extracted_jd = clean_role_and_jd(designation_raw, company_canon)
                ctc_lpa, ctc_display = parse_ctc(ctc_raw, company_canon, designation_raw)
                slot_display = parse_offer_slot(offer_date, placement_type)

                wa_msg, em_subj, em_body = generate_outreach_templates(name, company_canon, clean_role, dept)

                placed_record = {
                    **candidate_record,
                    "placed_in_raw": placed_in_raw,
                    "company": company_canon,
                    "company_category": company_cat or "Private / MNC",
                    "sector": sector or "Technology",
                    "placement_type": placement_type,
                    "designation_raw": designation_raw,
                    "designation": clean_role,
                    "job_description": extracted_jd,
                    "ctc_raw": ctc_raw,
                    "ctc_lpa": ctc_lpa,
                    "ctc_display": ctc_display,
                    "offer_date": offer_date,
                    "slot_display": slot_display,
                    "whatsapp_message": wa_msg,
                    "whatsapp_link": f"https://wa.me/91{re.sub(r'[^0-9]', '', phone)}?text={urllib.parse.quote(wa_msg)}" if phone else "",
                    "email_subject": em_subj,
                    "email_body": em_body,
                    "email_link": f"mailto:{email}?subject={urllib.parse.quote(em_subj)}&body={urllib.parse.quote(em_body)}" if email else "",
                    "linkedin_search_link": f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(name + ' IIT Kharagpur ' + company_canon)}",
                }
                placed_students.append(placed_record)

                # Company aggregation
                c_entry = companies_dict[company_canon]
                c_entry["raw_names"].add(placed_in_raw)
                c_entry["seasons"][season_label] += 1
                if sector:
                    c_entry["sectors"].add(sector)
                if company_cat:
                    c_entry["company_categories"].add(company_cat)
                if dept:
                    c_entry["departments"][dept] += 1
                if degree:
                    c_entry["degrees"][degree] += 1
                if clean_role:
                    c_entry["designations"][clean_role] += 1
                if ctc_lpa is not None:
                    c_entry["ctc_list"].append((ctc_lpa, ctc_display))
                if cgpa_val is not None:
                    c_entry["cgpa_list"].append(cgpa_val)
                if offer_date:
                    c_entry["offer_dates"][offer_date] += 1
                if extracted_jd:
                    c_entry["jds"].add(extracted_jd)

                if placement_type == "PPO":
                    c_entry["ppo_count"] += 1
                else:
                    c_entry["non_ppo_count"] += 1

                c_entry["students"].append({
                    "name": placed_record["name"],
                    "rollno": rollno,
                    "dept": dept,
                    "degree": degree,
                    "cgpa": cgpa_val,
                    "season": season_label,
                    "designation": clean_role,
                    "ctc_display": ctc_display,
                    "ctc_lpa": ctc_lpa,
                    "phone": phone,
                    "email": email,
                    "placement_type": placement_type,
                    "slot": slot_display,
                    "whatsapp_link": placed_record["whatsapp_link"],
                    "email_link": placed_record["email_link"],
                    "linkedin_link": placed_record["linkedin_search_link"],
                })

                dept_counter[dept] += 1
                if sector:
                    sector_counter[sector] += 1
                degree_counter[degree] += 1
                placement_type_counter[placement_type] += 1
                season_counter[season_label] += 1

            all_candidates.append(candidate_record)

    print(f"Total merged candidates: {len(all_candidates)}")
    print(f"Total placed candidates: {len(placed_students)}")
    print(f"Total unique companies: {len(companies_dict)}")

    # Build company summaries
    companies_summary = []
    for c_name, data in companies_dict.items():
        total_hires = len(data["students"])
        ctc_vals = [c[0] for c in data["ctc_list"]]
        cgpa_vals = data["cgpa_list"]

        max_ctc = max(ctc_vals) if ctc_vals else 0.0
        min_ctc = min(ctc_vals) if ctc_vals else 0.0
        avg_ctc = round(sum(ctc_vals) / len(ctc_vals), 2) if ctc_vals else 0.0
        sorted_ctc = sorted(ctc_vals)
        median_ctc = sorted_ctc[len(sorted_ctc) // 2] if sorted_ctc else 0.0

        min_cgpa = min(cgpa_vals) if cgpa_vals else None
        max_cgpa = max(cgpa_vals) if cgpa_vals else None
        avg_cgpa = round(sum(cgpa_vals) / len(cgpa_vals), 2) if cgpa_vals else None
        sorted_cgpa = sorted(cgpa_vals)
        median_cgpa = sorted_cgpa[len(sorted_cgpa) // 2] if sorted_cgpa else None

        max_ctc_display = f"₹{max_ctc:.2f} LPA" if max_ctc < 100 else f"₹{max_ctc/100:.2f} Cr"
        if data["ctc_list"]:
            for val, disp in data["ctc_list"]:
                if val == max_ctc:
                    max_ctc_display = disp
                    break

        companies_summary.append({
            "name": c_name,
            "raw_names": list(data["raw_names"]),
            "total_hires": total_hires,
            "ppo_count": data["ppo_count"],
            "non_ppo_count": data["non_ppo_count"],
            "seasons": dict(data["seasons"]),
            "sectors": list(data["sectors"]) or ["Technology"],
            "company_categories": list(data["company_categories"]) or ["Private"],
            "max_ctc_lpa": max_ctc,
            "min_ctc_lpa": min_ctc,
            "avg_ctc_lpa": avg_ctc,
            "median_ctc_lpa": median_ctc,
            "max_ctc_display": max_ctc_display,
            "min_cgpa": min_cgpa,
            "max_cgpa": max_cgpa,
            "avg_cgpa": avg_cgpa,
            "median_cgpa": median_cgpa,
            "departments": dict(data["departments"].most_common()),
            "degrees": dict(data["degrees"].most_common()),
            "designations": [d[0] for d in data["designations"].most_common()],
            "job_descriptions": list(data["jds"]),
            "students": data["students"],
        })

    companies_summary.sort(key=lambda x: (x["total_hires"], x["max_ctc_lpa"]), reverse=True)
    placed_students.sort(key=lambda s: s["ctc_lpa"] or 0.0, reverse=True)

    all_ctcs = [s["ctc_lpa"] for s in placed_students if s["ctc_lpa"] is not None]
    all_cgpas = [s["cgpa"] for s in placed_students if s["cgpa"] is not None]
    sorted_all_ctc = sorted(all_ctcs)

    if placed_students and all_ctcs:
        top_placed = max(placed_students, key=lambda s: s["ctc_lpa"] or 0.0)
        highest_ctc_lpa = top_placed["ctc_lpa"]
        highest_ctc_display = f"{top_placed['ctc_display']} ({top_placed['company']})"
    else:
        highest_ctc_lpa = 0.0
        highest_ctc_display = "₹2.44 Cr (Optiver)"

    analytics = {
        "total_registered": len(all_candidates),
        "total_placed": len(placed_students),
        "placement_percentage": round(len(placed_students) / len(all_candidates) * 100.0, 1) if all_candidates else 0.0,
        "total_companies": len(companies_summary),
        "ppo_count": placement_type_counter.get("PPO", 0),
        "non_ppo_count": placement_type_counter.get("NON-PPO", 0),
        "highest_ctc_lpa": highest_ctc_lpa,
        "highest_ctc_display": highest_ctc_display,
        "avg_ctc_lpa": round(sum(all_ctcs) / len(all_ctcs), 2) if all_ctcs else 0.0,
        "median_ctc_lpa": sorted_all_ctc[len(sorted_all_ctc) // 2] if sorted_all_ctc else 0.0,
        "avg_cgpa": round(sum(all_cgpas) / len(all_cgpas), 2) if all_cgpas else 0.0,
        "median_cgpa": sorted(all_cgpas)[len(all_cgpas) // 2] if all_cgpas else 0.0,
        "seasons_breakdown": dict(season_counter),
        "missing_seasons": ["2024-25"],
        "season_notes": "Season 2024-25 dataset is currently pending / missing from CDC release. Available seasons are 2025-26, 2023-24, 2022-23, and 2021-22.",
        "top_recruiters": [
            {"company": c["name"], "hires": c["total_hires"], "max_ctc": c["max_ctc_display"]}
            for c in companies_summary[:20]
        ],
        "top_ctc_companies": [
            {"company": c["name"], "max_ctc_lpa": c["max_ctc_lpa"], "max_ctc_display": c["max_ctc_display"], "hires": c["total_hires"]}
            for c in sorted(companies_summary, key=lambda x: x["max_ctc_lpa"], reverse=True)[:20]
        ],
        "departments_placed": dict(dept_counter.most_common()),
        "sectors_placed": dict(sector_counter.most_common()),
        "degrees_placed": dict(degree_counter.most_common()),
        "ctc_brackets": {
            "> 70 LPA": sum(1 for c in all_ctcs if c >= 70.0),
            "40 - 70 LPA": sum(1 for c in all_ctcs if 40.0 <= c < 70.0),
            "25 - 40 LPA": sum(1 for c in all_ctcs if 25.0 <= c < 40.0),
            "15 - 25 LPA": sum(1 for c in all_ctcs if 15.0 <= c < 25.0),
            "< 15 LPA": sum(1 for c in all_ctcs if c < 15.0),
        },
    }

    # Save to disk
    with open(os.path.join(DATA_DIR, "placed_students.json"), "w", encoding="utf-8") as f:
        json.dump(placed_students, f, indent=2, ensure_ascii=False)

    with open(os.path.join(DATA_DIR, "companies_summary.json"), "w", encoding="utf-8") as f:
        json.dump(companies_summary, f, indent=2, ensure_ascii=False)

    with open(os.path.join(DATA_DIR, "placement_analytics.json"), "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    with open(os.path.join(DATA_DIR, "all_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2, ensure_ascii=False)

    print("Master multi-season repositories regenerated successfully!")


if __name__ == "__main__":
    process_all_placement_data()
