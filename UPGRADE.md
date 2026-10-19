# JobHunt workspace upgrade

The existing FastAPI entrypoint and service integrations are retained. `/` now serves a new responsive workspace. The placement hub remains at `/placements`.

## What changed

- Dashboard with counts from actual saved jobs, stages, generated packs, and activity.
- Live streamed job discovery, keyword/source/status/YC filters, sorting, bookmarking, and job research. Searches request 10 results per query by default; distinct roles at the same company are preserved. Search-result URLs must match retrieved evidence.
- Application studio creates a tailored PDF and LaTeX source, cover letter, cold outreach, keyword list, and before/after review. Downloads have stable artifact IDs and survive application restarts when the storage disk persists.
- Pipeline board supports dragging between stages, notes, follow-up dates, and CSV export. Applied counts include explicit manual status changes and confirmed agent receipts; generating a resume does not mean an application was sent.
- Candidate profile and configuration-status screens.
- Optional bounded browser agent for Lever and Greenhouse. It fills known fields, uploads the selected resume, and captures a private screenshot. Missing questions, login, CAPTCHA, and unsupported pages require manual completion. Submission needs a separate user click after review; a single attempt is made and a portal receipt is required for `Submitted`. Ambiguous outcomes stay `Unconfirmed` and are not retried automatically.
- xAI Responses API support with configurable model; explicit Groq alternative. No provider switch occurs after a request fails.
- Signed, random, expiring session cookies; no default password; login throttling; authentication across placement/data APIs; same-origin write checks. Existing sessions must sign in again.

## Run

Python 3.11+:

```sh
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
# Configure server-side values securely; never commit .env.
uvicorn main:app --host 127.0.0.1 --port 8000
```

For browser automation, run `playwright install chromium` locally. The Docker image installs Chromium and system dependencies. Set `ENABLE_APPLICATION_AGENT=true` only after the browser is available. Browser sessions live in the running process for up to 10 minutes and expire across restarts; use a single Uvicorn worker for preparation/submit continuity.

## Render

Deploy this branch or merge it into the branch linked to the Render service. Rebuild the Docker image. Keep existing `PASSWORD`, `TAVILY_API_KEY`, and Sheets secrets. For xAI set `LLM_PROVIDER=xai`, `XAI_API_KEY`, and a model your account can access (default `grok-4.7`). To retain Groq use `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL`.

Use a strong `PASSWORD`, `COOKIE_SECURE=true`, and `PUBLIC_ORIGIN=https://<your-render-host>`. Configure a persistent disk and set `JOBHUNT_DATA_DIR` to its exact mount path. A path variable alone does not provision a disk. On ephemeral hosting, use Google Sheets for pipeline history and export important documents before redeploys. The app does not provision paid hosting resources.

No credentials are accepted in the browser. Connection status reports configuration, not a successful live health check or sufficient credits. No live search or real application should be reported as verified until tested with configured accounts.

## Test

```sh
pip install pytest
python -m pytest tests/test_workspace.py
node --check static/workspace.js
```

The other existing test scripts call live services and are not part of the offline test suite.

## Honest project metrics

The implementation supports broad multi-query discovery; it cannot guarantee 100 unique open jobs on every search. Search freshness is not proof a job remains open. Track actual unique results, application counts, and time saved from real usage before claiming those figures. The backend has one FastAPI entrypoint and separate service modules; it is not literally a single-file implementation. The application agent covers supported straightforward ATS forms, not every job portal.
