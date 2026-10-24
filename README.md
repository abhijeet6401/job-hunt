# JobHunt Agent

## New workspace

The redesigned app adds a dashboard, filtered job discovery, an application studio (resume + cover letter + outreach + diff), a drag-and-drop pipeline, candidate profile, connection status, and an optional Lever/Greenhouse browser application agent. **See [UPGRADE.md](UPGRADE.md) for setup, verification, deployment, and the exact automation limits.**

xAI is supported through its Responses API (`LLM_PROVIDER=xai`, `XAI_API_KEY`, `XAI_MODEL`). Groq remains available with `LLM_PROVIDER=groq`. Documents and metadata use server storage, so configure a persistent disk before relying on them across redeploys. Applied counts reflect explicit tracked status changes or confirmed portal receipts; document generation alone is never counted as a submission.

A deployed AI-powered job discovery, resume tailoring, and cold outreach assistant. It finds relevant job openings across Wellfound, LinkedIn, and YC startups, tailors your LaTeX resume to specific JDs using Groq, compiles a PDF, and drafts personalized cold emails — all from a password-protected web UI accessible from any device.

---

## Screenshots

_Add screenshots here after first deploy._

---

## Setup — Local

```bash
git clone https://github.com/yourusername/jobhunt-agent
cd jobhunt-agent

# Install dependencies (Python 3.11+)
pip install -r requirements.txt

# Install pdflatex (macOS)
brew install --cask mactex-no-gui

# Install pdflatex (Ubuntu/Debian)
# sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra

# Copy env template and fill in your keys
cp .env.example .env

# Run locally
uvicorn main:app --reload
# Open http://localhost:8000
```

---

## Setup — Render Deployment

1. Fork or push this repo to GitHub.
2. Go to [render.com](https://render.com) → New → Web Service → connect your repo.
3. Render will auto-detect `render.yaml` and configure the build.
4. Go to Environment → add these variables:
   - `PASSWORD` — any password you want to use
   - `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
   - `TAVILY_API_KEY` — from [tavily.com](https://tavily.com)
   - `GOOGLE_SHEETS_ID` — the ID from your Google Sheet URL
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — the full JSON from your service account key file (paste as one line)
5. Click Deploy. First build takes ~3-4 minutes (installs texlive).

---

## NVIDIA-hosted AI (free development endpoint)

The AI provider can use NVIDIA's hosted NIM chat API. No GPU or model container is needed on Render.
Set these values in the Render service's Environment settings:

- `LLM_PROVIDER=nvidia`
- `NVIDIA_API_KEY` — your private NVIDIA Developer API key; never commit it.
- `NVIDIA_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b` — or another accessible hosted chat model.

Obtain a key at https://build.nvidia.com/settings/api-keys. Hosted model availability and free
development limits can change; confirm the model's Free Endpoint status in NVIDIA's catalog.
The adapter does not fall back to xAI or Groq when NVIDIA fails. Existing xAI and Groq
configurations remain available by selecting their provider explicitly.

The Connections screen reports the provider, model, and whether a key is configured; it does
not prove the key is valid or that live inference has succeeded. NVIDIA errors report safe
setup or rate-limit guidance without returning raw provider responses. Tavily and Google
Sheets require their own credentials. Save the environment settings and deploy to apply them.

## Adding Your Resume

Replace the placeholder content in each file under `resumes/`:

```
resumes/
├── product.tex          # Product Manager / APM
├── founders_office.tex  # Founder's Office / Chief of Staff
├── data_analyst.tex     # Data Analyst / Growth Analyst
└── operations.tex       # Operations / Program Manager
```

Each file is a standard LaTeX document. The AI rewriting system targets `\item` lines (bullet points) and adjusts language to match a specific job description. It never adds experience that is not already in the file.

---

## Google Sheets Setup

1. Create a new Google Sheet.
2. Copy the Sheet ID from the URL: `docs.google.com/spreadsheets/d/SHEET_ID_HERE/`
3. Create a Service Account in Google Cloud Console → APIs & Services → Credentials.
4. Enable the Google Sheets API for your project.
5. Download the service account JSON key.
6. Share the Google Sheet with the service account email (Editor access).
7. Paste the full JSON as the `GOOGLE_SERVICE_ACCOUNT_JSON` env var.

The app auto-creates tabs: **Jobs**, **Applications**, **Outreach**.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | Python, FastAPI |
| Frontend | Vanilla JS, single HTML file |
| LLM | Groq API — llama-3.3-70b-versatile |
| Job Search | Tavily Web Search API |
| Database | Google Sheets (Service Account) |
| PDF | pdflatex (texlive) |
| Deployment | Render (free tier) |
| Auth | Session cookie, SHA-256 hashed password |

---

## Note

Built as a personal productivity tool and an AI engineering portfolio project. The architecture is intentionally simple: no React, no database, no message queue. Every component is replaceable and the entire system fits in ~600 lines of Python.
