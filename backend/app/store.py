"""Run persistence (SQLite) plus a tiny in-memory pub/sub for live updates."""

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.getenv("VENTUREDESK_DB", os.path.join(os.path.dirname(__file__), "..", "venturedesk.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            )"""
        )


def new_run(idea: str, company: str) -> dict[str, Any]:
    run = {
        "id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "idea": idea,
        "company": company,
        "status": "queued",
        "sections": {},
        "feedback": {},
        "error": None,
    }
    save_run(run)
    return run


def save_run(run: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (id, created_at, data) VALUES (?, ?, ?)",
            (run["id"], run["created_at"], json.dumps(run)),
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT data FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    runs = [json.loads(r["data"]) for r in rows]
    return [
        {"id": r["id"], "created_at": r["created_at"], "company": r["company"], "idea": r["idea"], "status": r["status"]}
        for r in runs
    ]


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
