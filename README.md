# Multi-Agent AI System for Business Operations

VentureDesk is an AI launch team for your business idea. Describe an idea and a team of Claude-powered agents turns it into an actionable launch plan, with you approving the work before it's finalised.

## How it works

```
 your idea
     │
     ▼
 Lead Strategist ── writes the brief
     │
     ▼
 ┌─────────┬───────────┬─────────┬───────┬───────┐
 │ Product │ Marketing │ Finance │ Legal │ Sales │   work in parallel, streamed live
 └─────────┴───────────┴─────────┴───────┴───────┘
     │
     ▼
 Reviewer ── finds conflicts and gaps between sections
     │
     ▼
 You ── approve, or send feedback to specific specialists (they redo it, reviewer re-checks)
     │
     ▼
 Lead Strategist ── writes the final launch plan (downloadable as Markdown)
```

## Stack

- **Backend:** Python, FastAPI, the Anthropic Python SDK, SQLite. Updates stream to the browser with Server-Sent Events.
- **Frontend:** React and Vite.
- **No external services** beyond the Claude API: no Docker, Redis or vector database.

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

Open http://localhost:5173.

No API key yet? Set `VENTUREDESK_DEMO=1` in `backend/.env` to try the full flow with placeholder output.

## Project layout

```
backend/app/
  agents.py     the team: roles, deliverables and prompts
  pipeline.py   run lifecycle: brief → specialists → review → approval → final plan
  llm.py        Claude streaming client (plus demo mode)
  store.py      SQLite persistence and live event fan-out
  main.py       REST + SSE API
frontend/src/
  NewRun.jsx    idea form, team overview, past runs
  RunView.jsx   live run view, approval panel, final plan
```

## Customising the team

Add or edit entries in `SPECIALISTS` in `backend/app/agents.py`. The pipeline, API and UI pick up new specialists automatically.

## License

MIT
