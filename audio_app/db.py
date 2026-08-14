"""
Storage layer for the audio app.

If SUPABASE_URL + SUPABASE_SERVICE_KEY are set (see ../supabase/README.md),
everything goes into the real `audio_submissions` / `people` tables from
Task 1's schema, and we try to link each submission to an existing person by
matching normalized phone (falls back to email if you extend the form).

If those env vars are NOT set, the app falls back to a local SQLite file
(`local.db`) with an equivalent schema, so `python app.py` works immediately
with zero setup for a quick local demo.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "local.db")


def _local_conn():
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_local_db():
    conn = _local_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audio_submissions (
            id TEXT PRIMARY KEY,
            person_id TEXT,
            submitted_name TEXT NOT NULL,
            submitted_phone TEXT NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            duration_seconds REAL,
            sample_rate_hz INTEGER,
            bitrate_kbps REAL,
            loudness_db REAL,
            noise_estimate TEXT,
            status TEXT DEFAULT 'received',
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id TEXT PRIMARY KEY,
            full_name TEXT,
            primary_phone TEXT,
            primary_email TEXT
        )
    """)
    conn.commit()
    conn.close()


def _normalize_phone_10(phone: str):
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    return digits[-10:] if len(digits) >= 10 else digits or None


def find_or_create_person(name: str, phone: str):
    """Best-effort link to Task 1's people table by phone. Returns person_id or None."""
    norm_phone = _normalize_phone_10(phone)
    if USE_SUPABASE:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        if norm_phone:
            res = sb.table("people").select("id").eq("primary_phone", norm_phone).execute()
            if res.data:
                return res.data[0]["id"]
        # not found -> create a minimal person record so the audio submission has somewhere to link
        res = sb.table("people").insert({
            "full_name": name,
            "primary_phone": norm_phone,
            "source_systems": ["audio_app"],
        }).execute()
        return res.data[0]["id"]
    else:
        conn = _local_conn()
        row = None
        if norm_phone:
            row = conn.execute("SELECT id FROM people WHERE primary_phone = ?", (norm_phone,)).fetchone()
        if row:
            conn.close()
            return row["id"]
        pid = str(uuid.uuid4())
        conn.execute("INSERT INTO people (id, full_name, primary_phone) VALUES (?, ?, ?)",
                     (pid, name, norm_phone))
        conn.commit()
        conn.close()
        return pid


def save_submission(record: dict):
    record = dict(record)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    record.setdefault("status", "processed")

    if USE_SUPABASE:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        sb.table("audio_submissions").insert(record).execute()
    else:
        conn = _local_conn()
        conn.execute("""
            INSERT INTO audio_submissions
            (id, person_id, submitted_name, submitted_phone, file_path, original_filename,
             duration_seconds, sample_rate_hz, bitrate_kbps, loudness_db, noise_estimate,
             status, created_at)
            VALUES (:id, :person_id, :submitted_name, :submitted_phone, :file_path, :original_filename,
                    :duration_seconds, :sample_rate_hz, :bitrate_kbps, :loudness_db, :noise_estimate,
                    :status, :created_at)
        """, record)
        conn.commit()
        conn.close()
    return record["id"]


def list_submissions():
    if USE_SUPABASE:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = sb.table("audio_submissions").select("*").order("created_at", desc=True).execute()
        return res.data
    else:
        conn = _local_conn()
        rows = conn.execute("SELECT * FROM audio_submissions ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]


if not USE_SUPABASE:
    init_local_db()
