"""VentureDesk API."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import agents, llm, pipeline, store

# Runs with work in progress live here so live views see partially streamed text.
active: dict[str, dict[str, Any]] = {}
tasks: set[asyncio.Task] = set()

BUSY = {"queued", "drafting_brief", "specialists_working", "reviewing", "writing_plan"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="VentureDesk API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewRun(BaseModel):
    idea: str = Field(min_length=10, max_length=4000)
    company: str = Field(default="", max_length=120)


class Revision(BaseModel):
    feedback: dict[str, str]


def _load(run_id: str) -> dict[str, Any]:
    run = active.get(run_id) or store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _launch(run: dict[str, Any], coro) -> None:
    run["status"] = "queued"  # claim the run now so a double-click can't start it twice
    active[run["id"]] = run

    async def wrapper():
        try:
            await coro
        finally:
            active.pop(run["id"], None)

    task = asyncio.create_task(wrapper())
    tasks.add(task)
    task.add_done_callback(tasks.discard)


@app.get("/api/health")
def health():
    return {"ok": True, "model": llm.MODEL, "demo": llm.DEMO_MODE}


@app.get("/api/team")
def team():
    return [{"key": s.key, "title": s.title, "focus": s.focus} for s in agents.SPECIALISTS]


@app.get("/api/runs")
def runs():
    return store.list_runs()


@app.post("/api/runs", status_code=201)
async def create_run(body: NewRun):
    run = store.new_run(body.idea.strip(), body.company.strip())
    _launch(run, pipeline.start(run))
    return run


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return _load(run_id)


@app.post("/api/runs/{run_id}/revise")
async def revise(run_id: str, body: Revision):
    run = _load(run_id)
    if run["status"] != "awaiting_approval":
        raise HTTPException(409, "This run isn't waiting for approval")
    feedback = {k: v.strip() for k, v in body.feedback.items() if k in agents.SPECIALISTS_BY_KEY and v.strip()}
    if not feedback:
        raise HTTPException(400, "Add feedback for at least one specialist")
    _launch(run, pipeline.revise(run, feedback))
    return {"ok": True}


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str):
    run = _load(run_id)
    if run["status"] != "awaiting_approval":
        raise HTTPException(409, "This run isn't waiting for approval")
    _launch(run, pipeline.approve(run))
    return {"ok": True}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request):
    run = _load(run_id)
    queue = store.bus.subscribe(run_id)

    async def stream():
        try:
            yield f"data: {json.dumps({'type': 'snapshot', 'run': run})}\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            store.bus.unsubscribe(run_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream")
