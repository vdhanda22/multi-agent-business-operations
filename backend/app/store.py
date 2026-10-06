"""Persistence (SQLite) for businesses, their knowledge library, runs and the activity log,
plus a tiny in-memory pub/sub for live updates."""

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.getenv("VENTUREDESK_DB", os.path.join(os.path.dirname(__file__), "..", "venturedesk.db"))

DOC_KINDS = ("sop", "knowledge")
LIBRARY_CHAR_LIMIT = 400_000  # roughly 100k tokens shared by every agent call


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS businesses (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                ts TEXT NOT NULL,
                agent TEXT NOT NULL,
                kind TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                metrics TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_docs_business ON documents(business_id);
            CREATE INDEX IF NOT EXISTS idx_runs_business ON runs(business_id);
            CREATE INDEX IF NOT EXISTS idx_activity_run ON activity(run_id);
            """
        )


# ---- Businesses -------------------------------------------------------------

def create_business(name: str, description: str) -> dict[str, Any]:
    biz = {"id": _id(), "name": name, "description": description, "created_at": _now()}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO businesses (id, name, description, created_at) VALUES (:id, :name, :description, :created_at)",
            biz,
        )
    return biz


def update_business(business_id: str, name: str, description: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE businesses SET name = ?, description = ? WHERE id = ?", (name, description, business_id))


def delete_business(business_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM businesses WHERE id = ?", (business_id,))


def get_business(business_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    return dict(row) if row else None


def list_businesses() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT b.*,
                      (SELECT COUNT(*) FROM documents d WHERE d.business_id = b.id) AS document_count,
                      (SELECT COUNT(*) FROM runs r WHERE r.business_id = b.id) AS run_count
               FROM businesses b ORDER BY b.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


# ---- Knowledge library ------------------------------------------------------

def list_documents(business_id: str, with_content: bool = False) -> list[dict[str, Any]]:
    cols = "*" if with_content else "id, business_id, kind, title, created_at, LENGTH(content) AS chars"
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {cols} FROM documents WHERE business_id = ? ORDER BY kind, title", (business_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def library_size(business_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(content)), 0) AS n FROM documents WHERE business_id = ?", (business_id,)
        ).fetchone()
    return row["n"]


def add_document(business_id: str, kind: str, title: str, content: str) -> dict[str, Any]:
    doc = {"id": _id(), "business_id": business_id, "kind": kind, "title": title, "content": content, "created_at": _now()}
    with _connect() as conn:
        conn.execute(
            "INSERT INTO documents (id, business_id, kind, title, content, created_at) "
            "VALUES (:id, :business_id, :kind, :title, :content, :created_at)",
            doc,
        )
    return doc


def get_document(doc_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def delete_document(doc_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ---- Runs -------------------------------------------------------------------

def new_run(business_id: str, idea: str, company: str) -> dict[str, Any]:
    run = {
        "id": _id(),
        "business_id": business_id,
        "created_at": _now(),
        "idea": idea,
        "company": company,
        "status": "queued",
        "sections": {},
        "feedback": {},
        "error": None,
    }
    save_run(run)
    return run


def public_run(run: dict[str, Any]) -> dict[str, Any]:
    """Drop in-memory working fields (prefixed with _) before saving or sending a run."""
    return {k: v for k, v in run.items() if not k.startswith("_")}


def save_run(run: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            # Upsert, not INSERT OR REPLACE: a replace deletes the row and would cascade-delete its activity log.
            "INSERT INTO runs (id, business_id, created_at, data) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (run["id"], run.get("business_id"), run["created_at"], json.dumps(public_run(run))),
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_runs(business_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query = "SELECT data FROM runs"
    args: tuple = ()
    if business_id:
        query += " WHERE business_id = ?"
        args = (business_id,)
    query += " ORDER BY created_at DESC LIMIT ?"
    with _connect() as conn:
        rows = conn.execute(query, (*args, limit)).fetchall()
    fields = ("id", "business_id", "created_at", "company", "idea", "status")
    return [{k: json.loads(r["data"]).get(k) for k in fields} for r in rows]


# ---- Activity log -----------------------------------------------------------

def log_activity(run_id: str, agent: str, kind: str, detail: str = "", metrics: dict | None = None) -> dict[str, Any]:
    entry = {"ts": _now(), "agent": agent, "kind": kind, "detail": detail, "metrics": metrics}
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO activity (run_id, ts, agent, kind, detail, metrics) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, entry["ts"], agent, kind, detail, json.dumps(metrics) if metrics else None),
        )
    entry["id"] = cur.lastrowid
    bus.publish(run_id, {"type": "activity", "entry": entry})
    return entry


def list_activity(run_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM activity WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    out = []
    for r in rows:
        e = dict(r)
        e["metrics"] = json.loads(e["metrics"]) if e["metrics"] else None
        out.append(e)
    return out


# ---- Live events ------------------------------------------------------------

class EventBus:
    """Fan out run events to every open browser tab watching that run."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        self._subscribers.get(run_id, set()).discard(q)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        for q in self._subscribers.get(run_id, set()):
            q.put_nowait(event)


bus = EventBus()
