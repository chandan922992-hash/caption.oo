#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT="${CLEAPYFLY_BACKEND_PORT:-8734}"

if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install --no-audit --no-fund)
fi

if [ ! -d frontend/dist ]; then
  (cd frontend && npm run build)
fi

backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --app-dir backend
