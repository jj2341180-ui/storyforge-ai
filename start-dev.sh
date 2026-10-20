#!/usr/bin/env bash
# Development mode: API on :8000 and Vite dev server on :5173 with hot reload.
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source backend/.venv/bin/activate
(cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
API_PID=$!
(cd frontend && npm run dev) &
UI_PID=$!
trap 'kill $API_PID $UI_PID 2>/dev/null || true' EXIT
wait
