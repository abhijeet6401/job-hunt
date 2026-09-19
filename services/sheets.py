"""
Google Sheets integration using a Service Account.

Input: tab name + row data as a list, or tab name + row index + new status.
Output: None on write, list of lists on read.

Authentication uses GOOGLE_SERVICE_ACCOUNT_JSON env var (full JSON string).
"""

import os
import json
import time
import logging
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column headers for each managed tab
TAB_HEADERS = {
    "Jobs": [
        "Date Found", "Date Posted", "Company", "Role Title", "Salary", "Location",
        "Source", "URL", "Recruiter Email", "One-Line Summary", "Role Type", "Status",
        "Source Type", "Match Score",
    ],
    "Applications": [
        "Date", "Company", "Role Title", "Role Type", "JD Summary",
        "Resume Version Used", "Key Changes Made", "PDF Filename", "Status",
    ],
    "Outreach": [
        "Date", "Company", "Contact Name", "Contact Role",
        "Email Draft 1", "Email Draft 2", "Sent", "Reply Received", "Notes", "Status",
    ],
    "Form Answers": [
        "Date", "Company", "Question", "Generated Answer", "Word Count", "Used",
    ],
}


LOCAL_DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "local_sheets_db.json")


def _is_sheets_enabled() -> bool:
    """Return True if real Google Service Account credentials and Sheet ID are present."""
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "").strip()
    if not raw_json or not sheet_id or "..." in raw_json:
        return False
    try:
        data = json.loads(raw_json)
        return bool(data.get("token_uri") and data.get("client_email"))
    except Exception:
        return False


def _load_local_db() -> dict[str, list[list[Any]]]:
    """Load local JSON storage fallback when Google Sheets is not configured."""
    if os.path.exists(LOCAL_DB_FILE):
        try:
            with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read local sheets DB: {e}")
    db = {}
    for tab, headers in TAB_HEADERS.items():
        db[tab] = [headers]
    return db


def _save_local_db(db: dict[str, list[list[Any]]]):
    """Persist local JSON storage fallback."""
    try:
        os.makedirs(os.path.dirname(LOCAL_DB_FILE), exist_ok=True)
        with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write local sheets DB: {e}")


def _get_service():
    """Build and return an authenticated Google Sheets API service client if configured."""
    if not _is_sheets_enabled():
        return None

    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds_dict = json.loads(raw_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    return service


def _get_sheet_id() -> str:
    """Return the Google Sheets document ID from environment."""
    return os.environ.get("GOOGLE_SHEETS_ID", "")


def _ensure_tab_exists(service, spreadsheet_id: str, tab_name: str):
    """
    Create a tab with header row if it does not already exist.

    Checks existing sheet titles and adds a new sheet + header row if missing.
    """
    if not service or not spreadsheet_id:
        return
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if tab_name not in existing:
        body = {
            "requests": [{
                "addSheet": {
                    "properties": {"title": tab_name}
                }
            }]
        }
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

        headers = TAB_HEADERS.get(tab_name, [])
        if headers:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()


def _retry(fn, retries: int = 3, delay: float = 2.0):
    """Run fn, retrying on HttpError up to `retries` times with `delay` seconds between attempts."""
    for attempt in range(retries):
        try:
            return fn()
        except HttpError as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"Sheets API error (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
            time.sleep(delay)


def append_row(tab_name: str, row_data: list[Any]):
    """
    Append a single row to the named tab in the configured Google Sheet (or local DB fallback).
    """
    if _is_sheets_enabled():
        try:
            service = _get_service()
            sheet_id = _get_sheet_id()
            _ensure_tab_exists(service, sheet_id, tab_name)

            def _do_append():
                service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row_data]},
                ).execute()

            _retry(_do_append)
            return
        except Exception as e:
            logger.warning(f"Google Sheets append failed, saving to local DB instead: {e}")

    # Local fallback
    db = _load_local_db()
    if tab_name not in db:
        db[tab_name] = [TAB_HEADERS.get(tab_name, [])]
    db[tab_name].append(row_data)
    _save_local_db(db)


def read_all_rows(tab_name: str) -> list[list[Any]]:
    """
    Read all rows from the named tab (Google Sheets or local DB fallback).
    """
    if _is_sheets_enabled():
        try:
            service = _get_service()
            sheet_id = _get_sheet_id()
            _ensure_tab_exists(service, sheet_id, tab_name)

            def _do_read():
                result = service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=f"{tab_name}!A1:Z1000",
                ).execute()
                return result.get("values", [])

            return _retry(_do_read) or []
        except Exception as e:
            logger.warning(f"Google Sheets read failed, falling back to local DB: {e}")

    # Local fallback
    db = _load_local_db()
    return db.get(tab_name, [TAB_HEADERS.get(tab_name, [])])


def get_job_urls() -> set:
    """Return the set of all job URLs already saved in the Jobs tab."""
    rows = read_all_rows("Jobs")
    if len(rows) <= 1:
        return set()
    # URL is column index 7 (8th column, 0-based)
    return {row[7] for row in rows[1:] if len(row) > 7 and row[7]}


def read_jobs() -> dict:
    """
    Read all rows from the Jobs tab and convert to structured dicts.

    Returns:
        {
            "jobs":         list of job-board job dicts,
            "social_posts": list of social-post dicts,
            "last_updated": "YYYY-MM-DD" string of the most recent Date Found, or None,
        }

    Rows with Source Type == "Social Post" are separated from regular job rows.
    Column order matches TAB_HEADERS["Jobs"]:
        0  Date Found   1  Date Posted  2  Company    3  Role Title
        4  Salary       5  Location     6  Source     7  URL
        8  Recruiter Email / Contact    9  Summary / Snippet
        10 Role Type    11 Status       12 Source Type  13 Match Score
    """
    rows = read_all_rows("Jobs")
    if len(rows) <= 1:
        return {"jobs": [], "social_posts": [], "last_updated": None}

    jobs: list[dict] = []
    social_posts: list[dict] = []
    last_updated: str | None = None

    for row in rows[1:]:
        # Pad to at least 14 columns so indexing is safe
        row = list(row) + [""] * max(0, 14 - len(row))

        date_found  = row[0]
        source_type = row[12] or "Job Board"
        status      = row[11] if row[11] in (
            "New", "Saved", "Shortlisted", "Applied", "Interviewing", "Offer", "Rejected"
        ) else "New"
        try:
            match_score = max(1, min(100, int(float(row[13]))))
        except (ValueError, TypeError):
            match_score = 50

        # Track the most recent Date Found across all rows
        if date_found and (last_updated is None or date_found > last_updated):
            last_updated = date_found

        if source_type == "Social Post":
            social_posts.append({
                "company":        row[2],
                "role_hiring":    row[3],
                "source":         row[6],
                "url":            row[7],
                "contact_method": row[8],
                "post_snippet":   row[9],
                "post_date":      row[1],
                "date_found":     date_found,
                "poster_name":    "Unknown",
                "poster_role":    "Unknown",
                "is_founder_post": False,
                "match_score":    match_score,
                "score_reason":   "",
                "status":         status,
                "source_type":    "Social Post",
            })
        else:
            jobs.append({
                "company":        row[2],
                "role":           row[3],
                "salary":         row[4],
                "location":       row[5],
                "source":         row[6],
                "url":            row[7],
                "recruiter_email": row[8],
                "summary":        row[9],
                "date_posted":    row[1],
                "date_found":     date_found,
                "match_score":    match_score,
                "score_reason":   "",
                "status":         status,
                "is_job":         True,
                "is_open":        True,
                "source_type":    source_type,
            })

    return {"jobs": jobs, "social_posts": social_posts, "last_updated": last_updated}


def clear_tab(tab_name: str):
    """
    Delete all data rows from the named tab, keeping the header row intact.
    """
    if _is_sheets_enabled():
        try:
            service  = _get_service()
            sheet_id = _get_sheet_id()
            _ensure_tab_exists(service, sheet_id, tab_name)

            def _do_clear():
                service.spreadsheets().values().clear(
                    spreadsheetId=sheet_id,
                    range=f"{tab_name}!A1:Z10000",
                ).execute()
                headers = TAB_HEADERS.get(tab_name, [])
                if headers:
                    service.spreadsheets().values().update(
                        spreadsheetId=sheet_id,
                        range=f"{tab_name}!A1",
                        valueInputOption="RAW",
                        body={"values": [headers]},
                    ).execute()

            _retry(_do_clear)
        except Exception as e:
            logger.warning(f"Google Sheets clear failed, clearing local DB instead: {e}")

    # Clear in local DB
    db = _load_local_db()
    headers = TAB_HEADERS.get(tab_name, [])
    db[tab_name] = [headers] if headers else []
    _save_local_db(db)


def update_job_status_by_url(url: str, new_status: str) -> bool:
    """
    Find the Jobs-tab row whose URL column matches and set its Status column.
    """
    if not url:
        return False

    updated_online = False
    if _is_sheets_enabled():
        try:
            service  = _get_service()
            sheet_id = _get_sheet_id()
            _ensure_tab_exists(service, sheet_id, "Jobs")

            def _do_read():
                result = service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range="Jobs!H1:H10000",
                ).execute()
                return result.get("values", [])

            url_rows = _retry(_do_read) or []

            target_row = None
            for i, row in enumerate(url_rows):
                if row and row[0] == url:
                    target_row = i + 1  # 1-indexed sheet row
                    break

            if target_row is not None:
                def _do_update():
                    service.spreadsheets().values().update(
                        spreadsheetId=sheet_id,
                        range=f"Jobs!L{target_row}",
                        valueInputOption="RAW",
                        body={"values": [[new_status]]},
                    ).execute()

                _retry(_do_update)
                updated_online = True
        except Exception as e:
            logger.warning(f"Google Sheets update status failed: {e}")

    # Always update in local DB too
    db = _load_local_db()
    jobs_rows = db.get("Jobs", [])
    updated_local = False
    for row in jobs_rows[1:]:
        if len(row) > 7 and row[7] == url:
            while len(row) < 14:
                row.append("")
            row[11] = new_status
            updated_local = True
            break
    if updated_local:
        _save_local_db(db)

    return updated_online or updated_local


def get_rejected_urls() -> set:
    """Return URLs of all Jobs-tab rows whose Status is 'Rejected' (never re-show these)."""
    rows = read_all_rows("Jobs")
    if len(rows) <= 1:
        return set()
    return {
        row[7] for row in rows[1:]
        if len(row) > 11 and row[7] and row[11] == "Rejected"
    }


def update_row_status(tab_name: str, row_index: int, new_status: str):
    """
    Update the Status column of a specific row (1-indexed, header is row 1).

    row_index=2 means the first data row. Uses the last column defined in TAB_HEADERS.
    """
    service = _get_service()
    sheet_id = _get_sheet_id()

    headers = TAB_HEADERS.get(tab_name, [])
    if not headers:
        raise ValueError(f"Unknown tab: {tab_name}")

    if _is_sheets_enabled():
        try:
            service = _get_service()
            sheet_id = _get_sheet_id()
            status_col_index = len(headers)
            col_letter = chr(ord("A") + status_col_index - 1)
            cell_range = f"{tab_name}!{col_letter}{row_index}"

            def _do_update():
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=cell_range,
                    valueInputOption="RAW",
                    body={"values": [[new_status]]},
                ).execute()

            _retry(_do_update)
        except Exception as e:
            logger.warning(f"Google Sheets update_row_status failed: {e}")

    # Local fallback
    db = _load_local_db()
    rows = db.get(tab_name, [])
    if row_index - 1 < len(rows):
        target = rows[row_index - 1]
        while len(target) < len(headers):
            target.append("")
        target[-1] = new_status
        _save_local_db(db)
