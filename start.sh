#!/usr/bin/env bash
# Starts the backend (port 8000) and frontend (port 5173) together. Ctrl+C stops both.
set -e
cd "$(dirname "$0")"

if [ -f backend/.env ]; then
  set -a; source backend/.env; set +a
fi

(cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload) &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT

cd frontend && npm run dev
