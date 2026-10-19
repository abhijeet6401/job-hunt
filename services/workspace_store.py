"""Private, transactional local workspace storage. Put STORAGE on a persistent disk."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

def storage():
    path = Path(os.getenv('JOBHUNT_DATA_DIR', 'storage')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

@contextmanager
def connect():
    db = sqlite3.connect(storage() / 'workspace.sqlite', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, payload TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(kind,id))')
    try:
        with db:
            yield db
    finally:
        db.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def put(kind, payload, record_id=None):
    record_id = record_id or uuid.uuid4().hex
    item = {**payload, 'id': record_id, 'updated_at': now()}
    with connect() as db:
        db.execute('INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated', (kind, record_id, json.dumps(item), item['updated_at']))
    return item

def get(kind, record_id):
    with connect() as db:
        row = db.execute('SELECT payload FROM records WHERE kind=? AND id=?', (kind, record_id)).fetchone()
    return json.loads(row['payload']) if row else None

def all_records(kind):
    with connect() as db:
        rows = db.execute('SELECT payload FROM records WHERE kind=? ORDER BY updated DESC', (kind,)).fetchall()
    return [json.loads(r['payload']) for r in rows]

def artifact(content, extension, label='document'):
    record_id = uuid.uuid4().hex
    path = storage() / (record_id + extension)
    path.write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))
    put('artifact', {'path': path.name, 'label': label, 'extension': extension}, record_id)
    return record_id

def artifact_path(record_id):
    item = get('artifact', record_id)
    if not item:
        raise FileNotFoundError('This document no longer exists. Generate it again.')
    path = storage() / item['path']
    if not path.is_file() or path.parent != storage():
        raise FileNotFoundError('This document no longer exists. Generate it again.')
    return path, item
