# Multi-Agent AI System for Business Operations

VentureDesk coordinates a team of specialised Claude agents (research, product, marketing, sales, CRM, operations, finance and legal) through a central command layer. Every agent works from the same business profile and SOP and knowledge library, every step is logged, and a human approves the work before the final plan is written. Business profiles are portable: export one and import it to redeploy the whole setup for another business.

## How it works

```
 business profile + SOP & knowledge library  ──► shared, cached context for every agent
                     │
 your goal ──► Command layer
                     │
                     ▼
            Lead Strategist ── writes the brief
                     │
                     ▼
            Research Lead ── live web search: market, competitors, customer signals
                     │
                     ▼
 ┌─────────┬───────────┬───────┬─────┬────────────┬─────────┬───────┐
 │ Product │ Marketing │ Sales │ CRM │ Operations │ Finance │ Legal │   in parallel, streamed live
 └─────────┴───────────┴───────┴─────┴────────────┴─────────┴───────┘
                     │
                     ▼
            Reviewer ── conflicts, gaps, SOP compliance
                     │
                     ▼
            You ── approve, or send feedback to specific specialists
                     │       (they redo their part, the reviewer re-checks)
                     ▼
            Lead Strategist ── final plan with a 90-day checklist (Markdown download)

 Activity log: every agent start/finish, status change, feedback and approval,
 with duration, tokens, cache hits, web searches and estimated cost.
```

## Features

- **Specialised agents.** Ten roles defined in one file (`backend/app/agents.py`). Add an entry and the pipeline, API and UI pick it up.
- **Central command layer.** `backend/app/pipeline.py` sequences the agents, runs specialists concurrently, handles revisions and enforces the human approval gate.
- **SOP and knowledge library.** Per-business documents (pasted or uploaded as `.md` or `.txt`) that every agent must follow and cite. The library is sent as a cached prompt prefix, so it's paid for in full once per run rather than once per agent.
- **Live research.** The Research Lead uses Claude's web search tool and cites sources.
- **Logging.** A persistent activity log per run, viewable live in the UI, with per-call token usage and cost estimates.
- **Redeployable.** Export a business profile as JSON and import it into any instance. See `examples/leafloop-profile.json`.

## Stack

- **Backend:** Python, FastAPI, the Anthropic Python SDK (`claude-opus-5-5`), SQLite. Live updates use Server-Sent Events.
- **Frontend:** React and Vite.
- **No other services:** no Docker, Redis or vector database.

## Setup

Requirements: Python 3.10+ and Node 18+.

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY

# Frontend
cd ../frontend
npm install
```

## Run

```bash
./start.sh
```

Open http://localhost:5173. Click **Import profile** and choose `examples/leafloop-profile.json` to start with a sample business that has SOPs.

No API key yet? Set `VENTUREDESK_DEMO=1` in `backend/.env` to try the full flow with placeholder output.

## Project layout

```
backend/app/
  agents.py      the team: roles, deliverables and prompts
  pipeline.py    command layer: brief → research → specialists → review → approval → final plan
  llm.py         Claude streaming client: shared-context caching, web search, usage and cost tracking
  store.py       SQLite: businesses, documents, runs, activity log, plus live event fan-out
  main.py        REST + SSE API
frontend/src/
  CommandCenter.jsx   businesses, team overview, recent runs, profile import
  BusinessView.jsx    profile, SOP & knowledge library, start a run, export
  RunView.jsx         live team output, approval panel, final plan
  ActivityLog.jsx     per-run log with token and cost totals
examples/
  leafloop-profile.json   sample business profile with SOPs
```

## License

MIT
