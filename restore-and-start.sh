#!/usr/bin/env bash
# Idempotent recovery script: recreates dependencies after a sandbox/VM reset and
# starts the StoryForge backend (port 8000) + Vite dev server (port 5173).
# Safe to run repeatedly. Source code, voices and data/ are never touched.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> [1/4] Python virtual environment + backend dependencies"
if [ ! -x "backend/.venv/bin/python" ]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -r backend/requirements.txt

echo "==> [2/4] Frontend dependencies"
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install --no-audit --no-fund)
fi

echo "==> [3/4] Production build (also served by the backend on :8000)"
(cd frontend && npm run build)

echo "==> [4/4] Starting services"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1
nohup backend/.venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --app-dir backend > data/backend.log 2>&1 &
echo $! > data/backend.pid
(cd frontend && nohup npm run dev > ../data/frontend.log 2>&1 &)

echo "Waiting for ports..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 1
done
echo "----------------------------------------"
curl -s http://127.0.0.1:8000/api/health && echo
echo "Backend (UI + API):  http://localhost:8000"
echo "Vite dev server:     http://localhost:5173"
echo "Logs: data/backend.log, data/frontend.log"
