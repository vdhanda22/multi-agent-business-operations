"""VentureDesk API."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import agents, llm, pipeline, store

# Runs with work in progress live here so live views see partially streamed text.
active: dict[str, dict[str, Any]] = {}
tasks: set[asyncio.Task] = set()


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


class BusinessIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class DocumentIn(BaseModel):
    kind: Literal["sop", "knowledge"]
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)


class BusinessExport(BusinessIn):
    documents: list[DocumentIn] = []


class NewRun(BaseModel):
    business_id: str
    idea: str = Field(min_length=10, max_length=4000)


class Revision(BaseModel):
    feedback: dict[str, str]


def _business(business_id: str) -> dict[str, Any]:
    biz = store.get_business(business_id)
    if not biz:
        raise HTTPException(404, "Business not found")
    return biz


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
    leads = [
        {"key": "brief", "title": "Lead Strategist", "focus": "writes the brief and the final plan", "stage": "lead"},
        {"key": "research", "title": "Research Lead", "focus": "live web research on market and competitors", "stage": "lead"},
    ]
    specialists = [{"key": s.key, "title": s.title, "focus": s.focus, "stage": "specialist"} for s in agents.SPECIALISTS]
    reviewer = [{"key": "review", "title": "Reviewer", "focus": "cross-checks everyone's work and SOP compliance", "stage": "review"}]
    return leads + specialists + reviewer


# ---- Businesses and their knowledge library ---------------------------------

@app.get("/api/businesses")
def businesses():
    return store.list_businesses()


@app.post("/api/businesses", status_code=201)
def create_business(body: BusinessIn):
    return store.create_business(body.name.strip(), body.description.strip())


@app.post("/api/businesses/import", status_code=201)
def import_business(body: BusinessExport):
    if sum(len(d.content) for d in body.documents) > store.LIBRARY_CHAR_LIMIT:
        raise HTTPException(413, "This profile's library is larger than the limit")
    biz = store.create_business(body.name.strip(), body.description.strip())
    for d in body.documents:
        store.add_document(biz["id"], d.kind, d.title.strip(), d.content)
    return biz


@app.get("/api/businesses/{business_id}")
def get_business(business_id: str):
    biz = _business(business_id)
    docs = store.list_documents(business_id)
    return {**biz, "documents": docs, "library_chars": sum(d["chars"] for d in docs), "library_limit": store.LIBRARY_CHAR_LIMIT}


@app.put("/api/businesses/{business_id}")
def update_business(business_id: str, body: BusinessIn):
    _business(business_id)
    store.update_business(business_id, body.name.strip(), body.description.strip())
    return {"ok": True}


@app.delete("/api/businesses/{business_id}")
def delete_business(business_id: str):
    _business(business_id)
    if any(r.get("business_id") == business_id for r in active.values()):
        raise HTTPException(409, "This business has a run in progress")
    store.delete_business(business_id)
    return {"ok": True}


@app.get("/api/businesses/{business_id}/export")
def export_business(business_id: str):
    """A portable profile: import it elsewhere to redeploy the same setup onto another instance."""
    biz = _business(business_id)
    docs = store.list_documents(business_id, with_content=True)
    return {
        "name": biz["name"],
        "description": biz["description"],
        "documents": [{"kind": d["kind"], "title": d["title"], "content": d["content"]} for d in docs],
    }


@app.post("/api/businesses/{business_id}/documents", status_code=201)
def add_document(business_id: str, body: DocumentIn):
    _business(business_id)
    if store.library_size(business_id) + len(body.content) > store.LIBRARY_CHAR_LIMIT:
        raise HTTPException(413, "The knowledge library is full. Remove a document or shorten this one.")
    doc = store.add_document(business_id, body.kind, body.title.strip(), body.content)
    return {k: v for k, v in doc.items() if k != "content"}


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    doc = store.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    store.delete_document(doc_id)
    return {"ok": True}


# ---- Runs -------------------------------------------------------------------

@app.get("/api/runs")
def runs(business_id: str | None = None):
    return store.list_runs(business_id)


@app.post("/api/runs", status_code=201)
async def create_run(body: NewRun):
    biz = _business(body.business_id)
    run = store.new_run(biz["id"], body.idea.strip(), biz["name"])
    _launch(run, pipeline.start(run))
    return store.public_run(run)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return store.public_run(_load(run_id))


@app.get("/api/runs/{run_id}/activity")
def activity(run_id: str):
    _load(run_id)
    return store.list_activity(run_id)


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
            snapshot = {"type": "snapshot", "run": store.public_run(run), "activity": store.list_activity(run_id)}
            yield f"data: {json.dumps(snapshot)}\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            store.bus.unsubscribe(run_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream")
