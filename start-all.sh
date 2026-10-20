#!/usr/bin/env bash
# Start StoryForge AI (Linux/macOS): builds the frontend if needed, then runs the backend,
# which serves both the API and the compiled UI on http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d "backend/.venv" ]; then
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate
pip install -q -r backend/requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install)
fi
(cd frontend && npm run build)

cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
