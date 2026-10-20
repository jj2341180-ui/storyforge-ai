#!/usr/bin/env bash
# One-command recovery after an Arena sandbox reset:
# rebuilds dependencies, restarts both app services, and opens a fresh public link.
# The new https://...trycloudflare.com URL is printed at the end and saved to PUBLIC-LINK.txt.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Restoring backend dependencies (if needed)"
[ -x backend/.venv/bin/python ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt

echo "==> Restoring frontend dependencies and rebuilding"
[ -d frontend/node_modules ] || (cd frontend && npm install --no-audit --no-fund)
(cd frontend && npm run build)

echo "==> Starting backend on :8000 and Vite on :5173"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1
nohup backend/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --app-dir backend > data/backend.log 2>&1 &
(cd frontend && nohup npm run dev > ../data/frontend.log 2>&1 &)

echo "==> Waiting for the backend"
for i in $(seq 1 40); do curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break; sleep 1; done

echo "==> Opening public tunnel (Cloudflare quick tunnel, no account needed)"
chmod +x ../bin/cloudflared 2>/dev/null || true
CF=$(command -v cloudflared || echo "$HOME/bin/cloudflared")
nohup "$CF" tunnel --url http://127.0.0.1:8000 --no-autoupdate > data/tunnel.log 2>&1 &
for i in $(seq 1 30); do
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" data/tunnel.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
echo "$URL" > PUBLIC-LINK.txt
echo "============================================================"
echo " YOUR PUBLIC LINK (open in Chrome/Safari on any device):"
echo "   $URL"
echo " Saved to PUBLIC-LINK.txt"
echo "============================================================"
