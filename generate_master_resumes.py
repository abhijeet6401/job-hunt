import os
import json

def generate_all_resumes():
    # 1. Master Comprehensive 2-Page CV (contains all roles and variants)
    master_cv_tex = r"""% ============================================================
% Abhijeet Kumar — Comprehensive Master Curriculum Vitae
% Indian Institute of Technology (IIT) Kharagpur
% Clean ATS-friendly LaTeX Format
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.4in,
  bottom=0.4in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}
\usepackage{tabularx}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing (M.Sc. 5Y) \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Education ----------
\section{Education}
\begin{center}
\small
\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llll}
\hline
\textbf{Year} & \textbf{Degree/Exam} & \textbf{Institute} & \textbf{CGPA/Marks} \\
\hline
2027 & 4YRS B.S. (Hons.) in Economics & Indian Institute of Technology (IIT) Kharagpur & 7.89 / 10 \\
2023 & CBSE Class 12th & Bhartiyam International School, Rudrapur & 97.00\% \\
2021 & CBSE Class 10th & Jaycees Public School, Rudrapur & 98.60\% \\
\hline
\end{tabular*}
\end{center}

\vspace{-2pt}

% ---------- Certifications ----------
\section{Certifications}
\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{Chartered Financial Analyst (CFA) L1 Candidate (Feb 2027):} Derivatives, Quant Methods, Economics, Fixed Income, Financial Statements.
  \item \textbf{Bloomberg Market Concepts (Dec 2025):} Fixed Income, Currencies, Economic Indicators, Commodity, Equity Options, Portfolio Management.
\end{itemize}

\vspace{-2pt}

% ---------- Internships ----------
\section{Internships}

\jobheader{Snabbit}{Strategised product roadmap across retention, launches, and unit cost economics to scale salon-at-home 5x nationally}{Product Management \& Business Strategy Intern | Bengaluru}{May'26 -- Sep'26}
\begin{achievelist}
  \achieve{Scaled retention GOV from 20\% to 50\% of total booking volume by designing and launching Blush Prive, a retention pass built in-app.}
  \achieve{Captured 15\%+ category order share by pricing and launching manicure \& pedicure, lifting AOV roughly 2x to Rs 2,000.}
  \achieve{Saved Rs 50L/month by renegotiating per-unit vendor pricing and consolidating volumes, cutting product cost from 40\% to 20\% of GOV.}
  \achieve{Negotiated a Rs 2Cr production order with 20+ manufacturers; managed Rs 30L inventory working capital cutting stock-outs 70\%.}
  \achieve{Owned RQSP performance across operations, sustaining 99\% fulfillment and 4.87 rating as daily orders scaled from 50 to 250.}
\end{achievelist}

\jobheader{Aequitas Investments}{Drove digital transformation at a \$1Bn AUM boutique fund to streamline Research, BD and Client workflows}{Finance and AI Strategy Intern | Mumbai}{Jun'25 -- Aug'25}
\begin{achievelist}
  \achieve{Cut analyst research time by 50\% by unifying 10+ news sources into a PERN + TypeScript research platform with MiniLM-based deduplication.}
  \achieve{Replaced Salesforce with a custom CRM serving 1,000+ HNI clients, automating lead tracking and deal pipelines for BD and onboarding teams.}
  \achieve{Cut client response time by 30\% by consolidating 5+ legacy tools into a platform optimizing comms across research, BD, ops, and fund teams.}
\end{achievelist}

\jobheader{Frost and Sullivan}{Delivered analytical insights and interactive solutions for sales strategy, demand forecasting, and inventory}{Business Analytics Intern | Mumbai}{May'25 -- Jun'25}
\begin{achievelist}
  \achieve{Executed predictive modeling using Moving Averages and Exponential Smoothing, deployed in Power BI with DAX and SQL integrations.}
  \achieve{Analyzed \$23M+ in multi-country sales data by building interactive Power BI dashboards and automating CAGR tracking via multi-level drilldowns.}
  \achieve{Estimated revenue across 3 segments, identifying 8.0\% product returns and Nov--Dec seasonality in demand cycles.}
\end{achievelist}

\jobheader{Felix Advisory}{Evaluated early-stage startup ecosystems by analyzing whitespace gaps, funding patterns, and sectoral tailwinds}{Research Intern | Gurgaon}{Mar'25 -- Apr'25}
\begin{achievelist}
  \achieve{Built sectoral intelligence models using Excel, Crunchbase, and Tracxn data; profiled startups and benchmarked verticals for investor decks.}
  \achieve{Drafted 3 investment reports analyzing \$1B+ funding patterns across Smart Manufacturing, Fintech, and Sports Tech.}
  \achieve{Mapped 6+ white space opportunities; shortlisted 20 seed/pre-seed startups aligned with macro shifts and emerging tech for deal sourcing.}
\end{achievelist}

\jobheader{3one4 Capital}{Assisted early-stage VC portfolio companies with financing strategies, growth optimization, and capital efficiency}{Portfolio Management and Strategy Intern | Bengaluru}{Dec'24 -- Feb'25}
\begin{achievelist}
  \achieve{Created debt financing playbooks comparing venture debt, NCDs, and RBF, analyzing costs (9--22\%) across 5 instruments and startup stages.}
  \achieve{Developed 4 briefs on bridge loans, asset financing, and convertible notes, helping founders extend runway up to 6 months while preserving equity.}
  \achieve{Supported 3 consumer and fintech startups (Seed-IPO) ex-CheQ on scaling decisions via analyzing unit economics, LTV/CAC, and growth patterns.}
\end{achievelist}

\jobheader{India Accelerator}{Conducted investment due diligence on early-stage startups, evaluating business models, metrics, and positioning}{Investment Analyst Intern | Gurgaon}{Aug'24 -- Oct'24}
\begin{achievelist}
  \achieve{Recommended a Pass (Execution Risk) post due diligence, applying TAM/SAM/SOM, ROI, and unit economics of 2 startups for VC deal filtering.}
  \achieve{Benchmarked 15+ competitors and mapped a \$130B market by analyzing Grest and ValueShoppe on pricing, GTM strategy, and user journeys.}
  \achieve{Synthesized insights from 20+ data sources on financials, CX gaps, and capital flows to assess investability in refurbished tech and B2B commerce.}
\end{achievelist}

\vspace{-2pt}

% ---------- Projects ----------
\section{Projects}

\textbf{JobHunt Agent | AI Automation | Self Project} \hfill \textbf{\small Jun'26} \\
\textit{\small Built a full-stack AI job discovery assistant that finds openings, auto-generates tailored resumes, and applies via autonomous agents}
\begin{achievelist}
  \achieve{Aggregated 100+ live job listings per search from LinkedIn and YC startups via Tavily API, tailoring LaTeX resumes to specific JDs using xAI's LLM.}
  \achieve{Generated role-specific cold outreach emails and tracked 30+ applications in Google Sheets by service account integration, saving 10+ hours.}
  \achieve{Deployed the assistant as a password-protected web app on Render by compiling resumes via pdflatex from a single-file FastAPI backend.}
\end{achievelist}

\textbf{Equity Research Reports | HAL - ACE | Self Project} \hfill \textbf{\small Jan'26} \\
\textit{\small Built LONG investment theses on HAL and ACE using DCF valuation, regression modeling, and risk-adjusted return benchmarking}
\begin{achievelist}
  \achieve{Built full equity report on HAL with DCF at Rs 7,660/share (\textasciitilde 53\% upside), comps of EV/EBITDA 17.7x, P/E 27.2x, and DuPont ROE 25.9\%.}
  \achieve{Projected 15\% CAGR in ACE revenue via regression with govt capex (adj $R^2$ 0.86, DCF at 14.56\% WACC, 0.935 Sharpe, 33.39\% Jensen's Alpha).}
\end{achievelist}

\textbf{Monetary-Fiscal Policy Divergence and Term Premium Analysis} \hfill \textbf{\small May'25} \\
\textit{\small Prof. Krittika Banerjee | IIT Kharagpur}
\begin{achievelist}
  \achieve{Estimated a 20 bps term premium rise when fiscal deficits >5\% GDP using a VECM model on 25 years of RBI, MOSPI, and CCIL data.}
  \achieve{Recommended barbell strategy of 50\% 91-day T-Bills and 50\% 15-year SDLs based on scenario analysis of RBI tightenings and yield shifts.}
\end{achievelist}

\textbf{Predictive Modelling of Airline Passenger Data | Course Project | IIT Kharagpur} \hfill \textbf{\small Jan'26 -- Feb'26} \\
\textit{\small Time-series econometric forecasting layering GARCH(1,1) on seasonal SARIMA residuals to quantify volatility}
\begin{achievelist}
  \achieve{Forecasted airline demand via SARIMA(1,1,1)(1,1,1)12, achieving $R^2$ of 0.96 and 2.3\% MAPE; diagnosed heteroskedasticity via ARCH-LM test.}
\end{achievelist}

\textbf{Personalised Credit Card Offer Recommendation System | Amex Decision Science Track} \hfill \textbf{\small Jul'25} \\
\textit{\small Ranking system to optimize credit card offer relevance leveraging customer behaviors and transaction history}
\begin{achievelist}
  \achieve{Built Ensemble of Experts and Rankers (E2R) with XGBoost \& LightGBM (MAP@7 0.652, 22.9\% lift); engineered features via NMF, UMAP, HDBSCAN.}
\end{achievelist}

\vspace{-2pt}

% ---------- Competitions & Conferences ----------
\section{Competitions \& Conferences}

\textbf{Winner | Product Management | General Championship | IIT Kharagpur} \hfill \textbf{\small Apr'25} \\
\begin{achievelist}
  \achieve{Pioneered design of full-stack insurance super-app integrating telemedicine, gig workers, and family management for B2B2C ecosystem.}
  \achieve{Defined roadmap to onboard 10M+ users, drive Rs 120 Cr premium growth, and cut claims costs 35\% via real-time AI claim tracking.}
\end{achievelist}

\textbf{Bronze | FRAMMER AI | Data Analytics General Championship | IIT Kharagpur} \hfill \textbf{\small Feb'26 -- Mar'26} \\
\begin{achievelist}
  \achieve{Architected full-stack FastAPI and Next.js platform orchestrating 4 GenAI engines via LangGraph for data analytics and KPI generation.}
  \achieve{Built self-healing SQL pipeline with 98\% success rate and G-Eval evaluation framework raising score from 60.4\% to 80.1\%.}
\end{achievelist}

\textbf{Runner up | Indian Case Challenge (ICC) | IIT Kharagpur} \hfill \textbf{\small Jan'25} \\
\begin{achievelist}
  \achieve{Placed 2nd among 2000+ global teams in Bikaji M\&A case (Loyka acquisition at Rs 156 Cr, 28\% IRR; supply chain efficiency +15\%).}
\end{achievelist}

\vspace{-2pt}

% ---------- Positions of Responsibility ----------
\section{Positions of Responsibility}

\textbf{Career Development Centre | Departmental Representative | IIT Kharagpur} \hfill \textbf{\small Sep'25 -- May'26}
\begin{achievelist}
  \achieve{Nominated from cohort of 350+ to 56-member core team facilitating placements for 6000+ students (fastest 1,800+ offers in all IITs).}
\end{achievelist}

\textbf{International Finance Student Association (IFSA) | Financial Analyst | IIT Kharagpur} \hfill \textbf{\small Aug'24 -- Apr'25}
\begin{achievelist}
  \achieve{Secured banking needs for 20+ IFSA chapters worldwide; built personal finance portfolios via Monte Carlo \& ARIMA; 1st in M\&A case.}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular Activities ----------
\section{Extra Curricular Activities}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students globally to spearhead community impact initiatives aligned with UN Sustainable Development Goals.
  \item \textbf{Quiz:} Represented IIT Kharagpur at Inter-IIT Cult Meet 6.0, 7.0, and 8.0 (Gold in India Quiz, overall Silver among 23 IITs); Bronze at InterIIT-IIM Nihilanth Quiz at IIMC (2024), IIML (2025), Silver at IITM (2026), and Gold at IIT KGP's General Championship '26.
  \item \textbf{Award:} Secured 14th rank in Uttarakhand for NTSE Scholarship; AIR 1487 in KVPY SA (2021--22) among 1 Lakh+ students.
  \item \textbf{Volunteer:} Led education programmes for 200+ underserved students and organized 5+ donation drives impacting 500+ people as NSS Unit leader.
  \item \textbf{Delegate:} Recognized among top 500 individuals worldwide, receiving an invitation from Harvard University for ACONF 2024 in Thailand.
  \item \textbf{Mentor:} Mentored 1000+ students for Joint Entrance Examination (JEE), providing academic and personal guidance at PhysicsWallah.
\end{itemize}

\vspace{-2pt}

% ---------- Skills & Expertise ----------
\section{Skills \& Expertise}

\noindent
\textbf{Programming Languages \& Libraries:} SQL (Adv), Python, C++, R, NumPy, Pandas, Matplotlib, Seaborn, Scikit-learn, Keras, React, TypeScript, APIs, LangGraph, FastAPI \\[2pt]
\textbf{Software \& Tools:} MS Excel (Adv), Power BI, DAX, PostgreSQL, R Studio, Jupyter, VS Code, Google Colab, GitHub, TradingView, Streamlit, Figma, Canva \\[2pt]
\textbf{Relevant Courses:} Econometrics, Corporate Valuation, Financial Management, Time Series (SARIMA, GARCH, VECM), Probability \& Statistics, Data Structures, AI in Economics

\end{document}
"""

    # 2. Product Management 1-Pager
    product_tex = r"""% ============================================================
% Abhijeet Kumar — Product Role Resume (1-Page ATS-Friendly)
% Indian Institute of Technology (IIT) Kharagpur
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.38in,
  bottom=0.38in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \quad | \quad \textbf{IIT Kharagpur} (CGPA: 7.89 / 10) \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Internships ----------
\section{Product \& Strategy Internships}

\jobheader{Snabbit}{Strategised product roadmap across retention, service launches, and cost optimisation to scale category 5x}{Product Management Intern | Bengaluru}{May'26 -- Sep'26}
\begin{achievelist}
  \achieve{Scaled retention GOV from 20\% to 50\% of total booking volume by designing and launching Blush Prive, an in-app retention membership pass.}
  \achieve{Captured 15\%+ of category order share by pricing and launching manicure \& pedicure as a new offering, lifting AOV roughly 2x to Rs 2,000.}
  \achieve{Owned RQSP metrics across daily operations, sustaining 99\% fulfillment and 4.87 average user rating as daily orders scaled from 50 to 250.}
\end{achievelist}

\jobheader{Aequitas Investments}{Drove digital transformation at a \$1Bn AUM boutique fund to streamline Research, BD and Client workflows}{AI Product Management Intern | Mumbai}{Jun'25 -- Aug'25}
\begin{achievelist}
  \achieve{Cut analyst research time by 50\% by unifying 10+ news sources into a PERN + TypeScript research platform with MiniLM-based deduplication.}
  \achieve{Replaced Salesforce with a custom CRM serving 1,000+ HNI clients, automating lead tracking and deal pipelines for BD and onboarding teams.}
  \achieve{Cut client response time by 30\% by consolidating 5+ legacy tools into a platform optimizing comms across research, BD, ops, and fund teams.}
\end{achievelist}

\jobheader{3one4 Capital}{Assisted early-stage VC portfolio companies with tailored financing strategies and growth optimization}{Portfolio Management and Strategy Intern | Bengaluru}{Dec'24 -- Feb'25}
\begin{achievelist}
  \achieve{Supported 3 consumer \& fintech startups (Seed-IPO) ex-CheQ on scaling decisions via analyzing unit economics, LTV/CAC, and growth patterns.}
  \achieve{Developed 4 briefs on bridge loans, asset financing, and convertible notes, helping founders extend runway up to 6 months while preserving equity.}
\end{achievelist}

\vspace{-2pt}

% ---------- Product Projects & Competitions ----------
\section{Product Projects \& Competitions}

\textbf{JobHunt Agent | AI Automation | Self Project} \hfill \textbf{\small Jun'26} \\
\textit{\small Built a full-stack AI job discovery assistant that finds relevant openings, auto-generates tailored resumes, and applies via agents}
\begin{achievelist}
  \achieve{Aggregated 100+ live job listings per search from LinkedIn and YC startups via Tavily API, tailoring LaTeX resumes to specific JDs using xAI's LLM.}
  \achieve{Generated role-specific cold outreach emails and tracked 30+ applications in Google Sheets by service account integration, saving 10+ hours.}
  \achieve{Deployed the assistant as a password-protected web app on Render by compiling resumes via pdflatex from a single-file FastAPI backend.}
\end{achievelist}

\textbf{Winner | Product Management | General Championship | IIT Kharagpur} \hfill \textbf{\small Apr'25} \\
\textit{\small Designed full-stack insurance super-app integrating telemedicine, gig workers, and family management for B2B2C ecosystem}
\begin{achievelist}
  \achieve{Defined scalable product roadmap to onboard 10M+ users, driving Rs 120 Cr premium growth and improving retention 30\% via fintech partnerships.}
  \achieve{Modelled 4 product modules, cutting claims costs 35\%, expanding rural access 40\%, and boosting UX via real-time AI claim tracking.}
\end{achievelist}

\textbf{Bronze | FRAMMER AI | Data Analytics General Championship | IIT Kharagpur} \hfill \textbf{\small Feb'26 -- Mar'26} \\
\textit{\small Full-stack Python/FastAPI and Next.js platform orchestrating 4 GenAI engines via LangGraph for data analytics and KPI generation}
\begin{achievelist}
  \achieve{Built self-healing SQL pipeline with 98\% execution success rate and G-Eval evaluation framework raising weighted evaluation from 60.4\% to 80.1\%.}
\end{achievelist}

\vspace{-2pt}

% ---------- Positions of Responsibility ----------
\section{Positions of Responsibility}

\textbf{Career Development Centre | Departmental Representative | IIT Kharagpur} \hfill \textbf{\small Sep'25 -- May'26}
\begin{achievelist}
  \achieve{Nominated from cohort of 350+ to 56-member core team managing recruitment operations for 6000+ students (fastest 1,800+ offers in all IITs).}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular Activities ----------
\section{Extra Curricular Activities \& Honors}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students globally to spearhead community impact aligned with UN SDGs.
  \item \textbf{Inter-IIT Quizzing:} Gold in India Quiz (Inter-IIT Cult Meet 6.0/7.0/8.0); Bronze at InterIIT-IIM Nihilanth Quiz at IIMC \& IIML, Silver at IITM (2026).
  \item \textbf{National Awards:} Secured 14th rank in Uttarakhand for NTSE Scholarship; All India Rank 1487 in KVPY SA (2021--22).
\end{itemize}

\vspace{-2pt}

% ---------- Skills & Expertise ----------
\section{Skills \& Technical Expertise}

\noindent
\textbf{Product Management:} PRD Writing, Product Roadmapping, User Story Mapping, Wireframing, GTM Strategy, Retention \& Funnel Analysis, Unit Economics \\[2pt]
\textbf{Technical Stack:} SQL (Adv), Python, React, TypeScript, Node.js, FastAPI, LangGraph, REST APIs, PostgreSQL, Git, Figma, Canva, Power BI

\end{document}
"""

    # 3. Data Analyst / Business Analytics 1-Pager
    data_analyst_tex = r"""% ============================================================
% Abhijeet Kumar — Data Analyst / Business Analytics Resume (1-Page)
% Indian Institute of Technology (IIT) Kharagpur
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.38in,
  bottom=0.38in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \quad | \quad \textbf{IIT Kharagpur} (CGPA: 7.89 / 10) \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Internships ----------
\section{Analytics \& Quantitative Internships}

\jobheader{Snabbit}{Drove data-backed decisions across procurement, retention and warehouse operations to scale category 5x}{Business Analyst Intern | Bengaluru}{May'26 -- Sep'26}
\begin{achievelist}
  \achieve{Queried Snabbit's database via SQL and built cost-to-revenue models in Excel, cutting product cost from 40\% to 20\% of services revenue.}
  \achieve{Built reorder-point and SKU-level tracking for 100+ SKUs across 2 warehouses, cutting stock-outs 70\% and limiting capital lock-up to Rs 30L.}
  \achieve{Tracked RQSP metrics via SQL queries and dashboards, sustaining 99\% fulfillment \& a 4.87 average rating as daily orders scaled from 50 to 250.}
\end{achievelist}

\jobheader{Frost and Sullivan}{Delivered analytical insights and interactive solutions to support sales strategy and inventory optimization}{Business Analytics Intern | Mumbai}{May'25 -- Jun'25}
\begin{achievelist}
  \achieve{Executed predictive modeling using Moving Averages and Exponential Smoothing, incorporated into Power BI Dashboards with DAX and SQL.}
  \achieve{Analyzed \$23M+ in multi-country sales data by building interactive Power BI dashboards and automating CAGR tracking via multi-level drilldowns.}
  \achieve{Estimated revenue across 3 segments, identifying 8.0\% product returns and Nov--Dec seasonality in demand cycles through time-series models.}
\end{achievelist}

\jobheader{Aequitas Investments}{Drove digital transformation at a \$1Bn AUM fund to streamline Research, BD and Client workflows}{AI Analytics Intern | Mumbai}{Jun'25 -- Aug'25}
\begin{achievelist}
  \achieve{Cut analyst research time by 50\% by unifying 10+ news sources into a PERN + TypeScript platform with MiniLM-based deduplication.}
  \achieve{Consolidated 5+ legacy tools into a unified platform, optimizing data tracking and client response time by 30\%.}
\end{achievelist}

\vspace{-2pt}

% ---------- Projects ----------
\section{Data Science \& Econometric Projects}

\textbf{Bronze | FRAMMER AI | Data Analytics General Championship | IIT Kharagpur} \hfill \textbf{\small Feb'26 -- Mar'26} \\
\textit{\small Full-stack Python/FastAPI and Next.js platform orchestrating 4 GenAI engines via LangGraph for data analytics and KPI generation}
\begin{achievelist}
  \achieve{Built a self-healing SQL pipeline that checks and rewrites failed queries, achieving a 98\% execution success rate and 88.2\% healing efficiency.}
  \achieve{Designed a G-Eval evaluation framework with execution-aware scoring, raising weighted evaluation from 60.4\% to 80.1\% across 4 metrics.}
\end{achievelist}

\textbf{Predictive Modelling of Airline Passenger Data | Course Project | IIT Kharagpur} \hfill \textbf{\small Jan'26 -- Feb'26} \\
\textit{\small Modelled airline passenger demand as seasonal time series layering GARCH(1,1) on SARIMA residuals for volatility forecast bands}
\begin{achievelist}
  \achieve{Forecasted airline demand via SARIMA(1,1,1)(1,1,1)12, achieving $R^2$ of 0.96 and 2.3\% MAPE by selecting orders on ADF, ACF/PACF, and AIC.}
  \achieve{Diagnosed heteroskedasticity via ARCH-LM tests; layered GARCH(1,1) to produce volatility-adjusted forecast bands, cutting 2-yr MAPE to 9.5\%.}
\end{achievelist}

\textbf{Personalised Credit Card Offer Recommendation System | Amex Decision Science Track} \hfill \textbf{\small Jul'25} \\
\textit{\small Ranking system to optimize credit card offer relevance leveraging customer behaviors and transaction history}
\begin{achievelist}
  \achieve{Built Ensemble of Experts and Rankers (E2R) model with XGBoost and LightGBM, achieving MAP@7 of 0.652, a 22.9\% lift over baseline.}
  \achieve{Engineered features by NMF, UMAP, and HDBSCAN and tuned via Optuna Bayesian search, improving AUC-PR >20\% and NDCG@7 by 18\%.}
\end{achievelist}

\textbf{Monetary-Fiscal Policy Divergence and Term Premium Analysis | IIT Kharagpur} \hfill \textbf{\small May'25} \\
\textit{\small Investigated fiscal-monetary policy divergence on long-term bond yields using economic time-series econometric modeling}
\begin{achievelist}
  \achieve{Built a VECM model on 25 years of RBI, MOSPI, and CCIL data, identifying a 20 bps term premium rise when fiscal deficits exceed 5\% of GDP.}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular & POR ----------
\section{Leadership \& Extra Curricular Activities}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{Career Development Centre (CDC):} Departmental Representative at IIT Kharagpur facilitating placement operations for 6000+ students.
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students worldwide to lead social impact projects aligned with UN SDGs.
  \item \textbf{National Quizzing:} Gold in India Quiz at Inter-IIT Cult Meet; Bronze at InterIIT-IIM Nihilanth Quiz (IIMC/IIML), Silver at IITM (2026).
  \item \textbf{Scholarships:} 14th rank in Uttarakhand for NTSE Scholarship; All India Rank 1487 in KVPY SA (2021--22).
\end{itemize}

\vspace{-2pt}

% ---------- Skills & Expertise ----------
\section{Technical Skills \& Tools}

\noindent
\textbf{Programming Languages:} SQL (Advanced), Python (Pandas, NumPy, Scikit-learn, Matplotlib, Seaborn, Keras), R, C++, TypeScript, HTML/CSS \\[2pt]
\textbf{Analytics \& BI:} Power BI, DAX, PostgreSQL, R Studio, Jupyter, Streamlit, Advanced Excel (financial modeling, VBA), Optuna, LangGraph \\[2pt]
\textbf{Quantitative Domains:} Econometrics, Time-Series Forecasting (SARIMA, GARCH, VECM), Machine Learning (XGBoost, LightGBM, Clustering)

\end{document}
"""

    # 4. Founder's Office & Strategy 1-Pager
    founders_office_tex = r"""% ============================================================
% Abhijeet Kumar — Founder's Office / Strategy / VC Resume (1-Page)
% Indian Institute of Technology (IIT) Kharagpur
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.38in,
  bottom=0.38in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \quad | \quad \textbf{IIT Kharagpur} (CGPA: 7.89 / 10) \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Internships ----------
\section{Founder's Office, Strategy \& VC Internships}

\jobheader{Snabbit}{Owned product, sourcing, vendor negotiations and unit cost economics to scale service line nationally}{Business Strategy Intern | Bengaluru}{May'26 -- Sep'26}
\begin{achievelist}
  \achieve{Saved Rs 50L/month by renegotiating per-unit vendor pricing and consolidating volumes, cutting product cost from 40\% to 20\% of GOV.}
  \achieve{Negotiated a Rs 2Cr production order speaking to 20+ manufacturers in India, screening 7 in person to secure target prices at scale.}
  \achieve{Owned Rs 30L in inventory working capital, implementing WMS and reorder points reducing stock-out frequency by roughly 70\%.}
\end{achievelist}

\jobheader{3one4 Capital}{Assisted early-stage VC portfolio companies with financing strategies and capital efficiency with Principal of Finance}{Portfolio Management and Strategy Intern | Bengaluru}{Dec'24 -- Feb'25}
\begin{achievelist}
  \achieve{Created debt financing playbooks comparing venture debt, NCDs, and RBF, analyzing costs (9--22\%) across 5 instruments and startup stages.}
  \achieve{Developed 4 briefs on bridge loans, asset financing, and convertible notes, helping founders extend runway up to 6 months while preserving equity.}
  \achieve{Supported 3 consumer \& fintech startups (Seed-IPO) ex-CheQ on scaling decisions via analyzing unit economics, LTV/CAC, and growth patterns.}
\end{achievelist}

\jobheader{Felix Advisory}{Evaluated early-stage startup ecosystems by analyzing whitespace gaps, funding patterns, and sectoral tailwinds}{Research Intern | Gurgaon}{Mar'25 -- Apr'25}
\begin{achievelist}
  \achieve{Built sectoral intelligence models using Excel, Crunchbase, and Tracxn data; profiled startups and benchmarked verticals for investor decks.}
  \achieve{Drafted 3 investment reports analyzing \$1B+ funding patterns across Smart Manufacturing, Fintech, and Sports Tech.}
  \achieve{Mapped 6+ white space opportunities; shortlisted 20 seed/pre-seed startups aligned with macro shifts and emerging tech for deal sourcing.}
\end{achievelist}

\jobheader{India Accelerator}{Conducted investment due diligence on early-stage startups, evaluating business models and financial metrics}{Investment Analyst Intern | Gurgaon}{Aug'24 -- Oct'24}
\begin{achievelist}
  \achieve{Recommended a Pass (Execution Risk) post due diligence, applying TAM/SAM/SOM, ROI, and unit economics of 2 startups for VC deal filtering.}
  \achieve{Benchmarked 15+ competitors and mapped a \$130B market by analyzing Grest and ValueShoppe on pricing, GTM strategy, and user journeys.}
\end{achievelist}

\vspace{-2pt}

% ---------- Projects & Competitions ----------
\section{Strategic Case Competitions \& Projects}

\textbf{Runner up | Indian Case Challenge (ICC) | IIT Kharagpur} \hfill \textbf{\small Jan'25} \\
\textit{\small Bikaji global expansion case competition, winning INR 50K prize, only undergraduate team on podium among 2000+ teams}
\begin{achievelist}
  \achieve{Evaluated 5+ M\&A targets, recommending Loyka for acquisition at an Rs 156 Cr valuation with a 28\% IRR on strategic and financial fitness.}
  \achieve{Improved supply chain efficiency by 15\% and cut stockouts by 40\% via ML-based Industry 5.0 demand forecasting and network flow models.}
\end{achievelist}

\textbf{JobHunt Agent | AI Automation | Self Project} \hfill \textbf{\small Jun'26} \\
\textit{\small Built a full-stack AI job discovery assistant that finds relevant openings, auto-generates tailored resumes, and automates applications}
\begin{achievelist}
  \achieve{Aggregated 100+ live listings via Tavily API; generated cold outreach emails and tracked 30+ applications in Google Sheets via service account.}
\end{achievelist}

\textbf{Equity Research Reports | HAL - ACE | Self Project} \hfill \textbf{\small Jan'26} \\
\textit{\small Built LONG investment theses on HAL and ACE using DCF valuation, regression modeling, and risk-adjusted return benchmarking}
\begin{achievelist}
  \achieve{Built full equity report on HAL with DCF at Rs 7,660/share (\textasciitilde 53\% upside), comps of EV/EBITDA 17.7x, P/E 27.2x, and DuPont ROE 25.9\%.}
\end{achievelist}

\vspace{-2pt}

% ---------- Positions of Responsibility ----------
\section{Positions of Responsibility}

\textbf{Career Development Centre | Departmental Representative | IIT Kharagpur} \hfill \textbf{\small Sep'25 -- May'26}
\begin{achievelist}
  \achieve{Nominated from cohort of 350+ to 56-member core team managing campus recruitment for 6000+ students (fastest 1,800+ offers in all IITs).}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular Activities ----------
\section{Extra Curricular Activities \& Honors}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students worldwide to lead social impact projects aligned with UN SDGs.
  \item \textbf{Inter-IIT Quizzing:} Gold in India Quiz at Inter-IIT Cult Meet; Bronze at InterIIT-IIM Nihilanth Quiz (IIMC/IIML), Silver at IITM (2026).
  \item \textbf{National Awards:} 14th rank in Uttarakhand for NTSE Scholarship; All India Rank 1487 in KVPY SA (2021--22).
\end{itemize}

\vspace{-2pt}

% ---------- Core Competencies ----------
\section{Core Competencies}

\noindent
\textbf{Strategic Operations:} Unit Economics, Sourcing \& Vendor Negotiations, TAM/SAM/SOM, Capital Efficiency, Venture Debt / NCDs / RBF \\[2pt]
\textbf{Financial Modeling \& Analytics:} DCF Valuation, M\&A Due Diligence, SQL, Python, Power BI, DAX, Advanced Excel, Econometrics

\end{document}
"""

    # 5. Operations / Program Management 1-Pager
    operations_tex = r"""% ============================================================
% Abhijeet Kumar — Operations / Program Manager Resume (1-Page)
% Indian Institute of Technology (IIT) Kharagpur
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.38in,
  bottom=0.38in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \quad | \quad \textbf{IIT Kharagpur} (CGPA: 7.89 / 10) \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Operations Experience ----------
\section{Operations \& Program Management Experience}

\jobheader{Snabbit}{Owned product, sourcing, vendor negotiations and unit cost economics to scale service line nationally}{Business Strategy \& Sourcing Intern | Bengaluru}{May'26 -- Sep'26}
\begin{achievelist}
  \achieve{Saved Rs 50L/month by renegotiating per-unit vendor pricing and consolidating volumes, cutting product cost from initial 40\% to 20\% of GOV.}
  \achieve{Negotiated a Rs 2Cr production order speaking to 20+ manufacturers in India, screening 7 in person to secure quality at target prices at scale.}
  \achieve{Owned Rs 30L in inventory working capital, implementing WMS, reorder points, and bin designs reducing stock-out frequency by roughly 70\%.}
  \achieve{Managed RQSP performance across daily operations, sustaining 99\% fulfillment and 4.87 rating as daily orders scaled from 50 to 250.}
\end{achievelist}

\jobheader{Aequitas Investments}{Drove workflow optimization and platform consolidation across 4+ business divisions}{Finance and Operations Intern | Mumbai}{Jun'25 -- Aug'25}
\begin{achievelist}
  \achieve{Consolidated 5+ legacy tools into a unified platform, optimizing communications and cutting client inquiry response time by 30\%.}
  \achieve{Cut research analyst processing time by 50\% unifying 10+ research feeds into an automated PERN pipeline with MiniLM deduplication.}
  \achieve{Built and deployed central CRM for 1000+ HNI clients, displacing Salesforce and automating deal pipelines for BD and onboarding teams.}
\end{achievelist}

\jobheader{Frost and Sullivan}{Supported demand planning and inventory optimization across US and international markets}{Growth Operations Intern | Mumbai}{May'25 -- Jun'25}
\begin{achievelist}
  \achieve{Supported inventory optimization and demand forecasting through predictive Moving Average and Exponential Smoothing models in Power BI.}
  \achieve{Diagnosed operational return patterns across 3 market segments, identifying an 8.0\% return rate and Q4 demand surge bottlenecks.}
\end{achievelist}

\vspace{-2pt}

% ---------- Scale Operations & Case Competitions ----------
\section{Scale Operations \& Quantitative Cases}

\textbf{Career Development Centre | Departmental Representative | IIT Kharagpur} \hfill \textbf{\small Sep'25 -- May'26}
\begin{achievelist}
  \achieve{Orchestrated campus recruitment operations and interview scheduling across 6000+ students as part of 56-member core execution committee.}
  \achieve{Served as primary liaison between corporate recruiters and students, coordinating PPTs, tests, GDs, and interviews for 3000+ candidates.}
  \achieve{Streamlined real-time placement tracking and incident resolution, contributing to the fastest 1,800+ job offers across all IITs.}
\end{achievelist}

\textbf{Runner up | Indian Case Challenge (ICC) | IIT Kharagpur} \hfill \textbf{\small Jan'25} \\
\textit{\small Bikaji global expansion case competition, winning INR 50K prize, only undergraduate team on podium among 2000+ teams}
\begin{achievelist}
  \achieve{Improved supply chain efficiency by 15\% and cut stockouts by 40\% via ML-based Industry 5.0 demand forecasting and network flow models.}
  \achieve{Evaluated operational synergies and post-merger integration for an Rs 156 Cr acquisition target (28\% projected IRR).}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular Activities ----------
\section{Leadership \& Extra Curricular Activities}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students worldwide to lead social impact projects aligned with UN SDGs.
  \item \textbf{NSS Unit Leader:} Led education programmes for 200+ underprivileged students and organized 5+ donation drives impacting 500+ people.
  \item \textbf{National Quizzing:} Gold in India Quiz at Inter-IIT Cult Meet; Bronze at InterIIT-IIM Nihilanth Quiz (IIMC/IIML), Silver at IITM (2026).
\end{itemize}

\vspace{-2pt}

% ---------- Skills & Expertise ----------
\section{Operations Skills \& Systems}

\noindent
\textbf{Operations Management:} Sourcing \& Vendor Negotiations, WMS, Inventory Optimization, SLA Management, Reorder Planning, RQSP Metrics \\[2pt]
\textbf{Software \& Systems:} Advanced Excel (VBA, Models), Power BI, DAX, SQL, Python, PostgreSQL, ERP/CRM Systems, Project Tracking (Notion, Jira)

\end{document}
"""

    # 6. Finance & Investing 1-Pager
    finance_tex = r"""% ============================================================
% Abhijeet Kumar — Finance & Investment Analysis Resume (1-Page)
% Indian Institute of Technology (IIT) Kharagpur
% ============================================================

\documentclass[10pt, a4paper]{article}

\usepackage[
  top=0.38in,
  bottom=0.38in,
  left=0.5in,
  right=0.5in
]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\usepackage{parskip}
\usepackage{fontawesome5}

\hypersetup{
  colorlinks=true,
  urlcolor=black,
  linkcolor=black
}

\pagestyle{empty}

\titleformat{\section}
  {\vspace{-4pt}\scshape\raggedright\large\bfseries}
  {}{0em}{}
  [\color{black}\titlerule \vspace{-3pt}]

\newcommand{\jobheader}[4]{
  \vspace{-1pt}
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} \quad | \quad #3 & \textbf{\small #4} \\
    \textit{\small #2} & \\
  \end{tabular*}
  \vspace{-2pt}
}

\newenvironment{achievelist}{
  \begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
    \small
}{
  \end{itemize}
  \vspace{-2pt}
}

\newcommand{\achieve}[1]{\item #1}

\begin{document}

% ---------- Header ----------
\begin{center}
  {\LARGE \textbf{ABHIJEET KUMAR}} \quad | \quad \textbf{23HS10002} \\[3pt]
  \textbf{B.S. (Hons.) in ECONOMICS} \quad | \quad \textbf{IIT Kharagpur} (CGPA: 7.89 / 10) \\[2pt]
  \small \textbf{Minor:} Mathematics \& Computing \quad | \quad \textbf{Micro Spl.:} Artificial Intelligence and Applications \\[3pt]
  \small
  \faPhone\ \href{tel:+916398985179}{+91 63989 85179} \quad | \quad
  \faEnvelope\ \href{mailto:kumarabhiitkgp@gmail.com}{kumarabhiitkgp@gmail.com} \quad | \quad
  \faLinkedin\ \href{https://linkedin.com/in/abhijeetkgp}{linkedin.com/in/abhijeetkgp} \quad | \quad
  \faGithub\ \href{https://github.com/abhijeet6401}{github.com/abhijeet6401}
\end{center}

\vspace{-4pt}

% ---------- Certifications ----------
\section{Certifications}
\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{Chartered Financial Analyst (CFA) L1 Candidate (Feb 2027):} Derivatives, Quant Methods, Economics, Fixed Income, Financial Statements.
  \item \textbf{Bloomberg Market Concepts (Dec 2025):} Fixed Income, Currencies, Economic Indicators, Commodity, Equity Options, Portfolio Management.
\end{itemize}

\vspace{-2pt}

% ---------- Internships ----------
\section{Finance, VC \& Investment Internships}

\jobheader{Aequitas Investments}{Digital transformation and tech strategy at a \$1Bn AUM boutique investment fund}{Finance and AI Strategy Intern | Mumbai}{Jun'25 -- Aug'25}
\begin{achievelist}
  \achieve{Cut analyst research time by 50\% by unifying 10+ news sources into a PERN + TypeScript research platform with MiniLM-based deduplication.}
  \achieve{Replaced Salesforce with a custom CRM serving 1,000+ HNI clients, automating lead tracking and deal pipelines for BD and fund teams.}
\end{achievelist}

\jobheader{3one4 Capital}{Assisted early-stage VC portfolio companies with tailored financing strategies, growth optimization, and capital efficiency}{Portfolio Management and Strategy Intern | Bengaluru}{Dec'24 -- Feb'25}
\begin{achievelist}
  \achieve{Created debt financing playbooks comparing venture debt, NCDs, and RBF, analyzing costs (9--22\%) across 5 instruments and startup stages.}
  \achieve{Developed 4 briefs on bridge loans, asset financing, and convertible notes, helping founders extend runway up to 6 months while preserving equity.}
  \achieve{Supported 3 consumer \& fintech startups (Seed-IPO) ex-CheQ on scaling decisions via analyzing unit economics, LTV/CAC, and growth patterns.}
\end{achievelist}

\jobheader{India Accelerator}{Conducted investment due diligence on early-stage startups, evaluating business models and financial metrics}{Investment Analyst Intern | Gurgaon}{Aug'24 -- Oct'24}
\begin{achievelist}
  \achieve{Recommended a Pass (Execution Risk) post due diligence, applying TAM/SAM/SOM, ROI, and unit economics of 2 startups for VC deal filtering.}
  \achieve{Benchmarked 15+ competitors and mapped a \$130B market by analyzing Grest and ValueShoppe on pricing, GTM strategy, and user journeys.}
\end{achievelist}

\jobheader{Felix Advisory}{Evaluated early-stage startup ecosystems by analyzing whitespace gaps, funding patterns, and sectoral tailwinds}{Research Intern | Gurgaon}{Mar'25 -- Apr'25}
\begin{achievelist}
  \achieve{Built sectoral intelligence models using Excel, Crunchbase, and Tracxn data; drafted 3 investment reports analyzing \$1B+ funding patterns.}
\end{achievelist}

\vspace{-2pt}

% ---------- Projects & Competitions ----------
\section{Financial Modeling, Projects \& Competitions}

\textbf{Equity Research Reports | HAL - ACE | Self Project} \hfill \textbf{\small Jan'26} \\
\textit{\small Built LONG investment theses on HAL and ACE using DCF valuation, regression modeling, and risk-adjusted return benchmarking}
\begin{achievelist}
  \achieve{Built full equity report on HAL with DCF at Rs 7,660/share (\textasciitilde 53\% upside), comps of EV/EBITDA 17.7x, P/E 27.2x, and DuPont ROE 25.9\%.}
  \achieve{Projected 15\% CAGR in ACE revenue via regression with govt capex (adj $R^2$ 0.86, DCF at 14.56\% WACC, 0.935 Sharpe, 33.39\% Jensen's Alpha).}
\end{achievelist}

\textbf{Monetary-Fiscal Policy Divergence and Term Premium Analysis | IIT Kharagpur} \hfill \textbf{\small May'25} \\
\textit{\small Investigated fiscal-monetary policy divergence on long-term bond yields using macroeconomic time series modeling}
\begin{achievelist}
  \achieve{Built a VECM model on 25 years of RBI, MOSPI, and CCIL data, identifying a 20 bps term premium rise when fiscal deficits exceed 5\% of GDP.}
  \achieve{Recommended barbell strategy of 50\% 91-day T-Bills and 50\% 15-year SDLs based on scenario analysis of RBI tightening cycles.}
\end{achievelist}

\textbf{Runner up | Indian Case Challenge (ICC) | IIT Kharagpur} \hfill \textbf{\small Jan'25} \\
\textit{\small Bikaji global expansion case competition, winning INR 50K prize, only undergraduate team on podium among 2000+ teams}
\begin{achievelist}
  \achieve{Evaluated 5+ M\&A targets, recommending Loyka for acquisition at an Rs 156 Cr valuation with a 28\% IRR on strategic and financial fitness.}
\end{achievelist}

\vspace{-2pt}

% ---------- Positions of Responsibility ----------
\section{Positions of Responsibility}

\textbf{International Finance Student Association (IFSA) | Financial Analyst | IIT Kharagpur} \hfill \textbf{\small Aug'24 -- Apr'25}
\begin{achievelist}
  \achieve{Coordinated with IFSA Network team to secure banking/sponsorship for 20+ chapters across LATAM, NA, EMEA, APAC.}
  \achieve{Designed personalised finance portfolios using Monte Carlo \& ARIMA across 5+ asset classes; 1st in intra-soc M\&A competition.}
\end{achievelist}

\vspace{-2pt}

% ---------- Extra Curricular Activities ----------
\section{Extra Curricular Activities}

\begin{itemize}[leftmargin=1.2em, itemsep=0.5pt, parsep=0pt, topsep=1pt]
  \small
  \item \textbf{UN Millennium Fellow:} Selected as one of 5,000 students worldwide to lead social impact projects aligned with UN SDGs.
  \item \textbf{Inter-IIT Quizzing:} Gold in India Quiz at Inter-IIT Cult Meet; Bronze at InterIIT-IIM Nihilanth Quiz (IIMC/IIML), Silver at IITM (2026).
  \item \textbf{Scholarships:} 14th rank in Uttarakhand for NTSE Scholarship; All India Rank 1487 in KVPY SA (2021--22).
\end{itemize}

\vspace{-2pt}

% ---------- Skills & Expertise ----------
\section{Finance Skills \& Tools}

\noindent
\textbf{Financial Valuation \& Strategy:} DCF Modeling, Trading Comps, DuPont Analysis, M\&A Due Diligence, Venture Debt, NCDs, RBF, TAM/SAM/SOM \\[2pt]
\textbf{Quantitative \& Tools:} Advanced Excel (DCF, sensitivity tables), Bloomberg Terminal, Python, SQL, Power BI, DAX, Time-Series (SARIMA, VECM)

\end{document}
"""

    files = {
        "resumes/master_cv.tex": master_cv_tex,
        "resumes/cv.tex": product_tex, # Default master 1-pager
        "resumes/product.tex": product_tex,
        "resumes/data_analyst.tex": data_analyst_tex,
        "resumes/founders_office.tex": founders_office_tex,
        "resumes/operations.tex": operations_tex,
        "resumes/finance_investing.tex": finance_tex,
    }

    for path, content in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated {path}")

if __name__ == "__main__":
    generate_all_resumes()
