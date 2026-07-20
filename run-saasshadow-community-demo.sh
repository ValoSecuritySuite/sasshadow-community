#!/usr/bin/env bash
set -euo pipefail

test -f requirements.txt && test -f frontend/package.json || { echo "Run from the sasshadow-community repository root."; exit 1; }

python -m pip install -r requirements.txt
test -d frontend/node_modules || npm --prefix frontend ci

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  nohup env APP_EDITION=community APP_LOG_LEVEL=INFO \
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >/tmp/saasshadow-community-api.log 2>&1 &
  echo $! >/tmp/saasshadow-community-api.pid
fi

for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:8000/health >/dev/null || { tail -n 200 /tmp/saasshadow-community-api.log; exit 1; }

if ! curl -fsS http://127.0.0.1:3000 >/dev/null 2>&1; then
  nohup env NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 \
    npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 3000 \
    >/tmp/saasshadow-community-web.log 2>&1 &
  echo $! >/tmp/saasshadow-community-web.pid
fi

for _ in $(seq 1 45); do curl -fsS http://127.0.0.1:3000 >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:3000 >/dev/null || { tail -n 200 /tmp/saasshadow-community-web.log; exit 1; }
echo "SaaSShadow Community demo ready: UI http://localhost:3000 | API docs http://localhost:8000/docs"

