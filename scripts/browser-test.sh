#!/bin/bash
# `make browser-test`: starts the backend and the frontend in demo mode (no model key, so no
# model call can happen), drives a real Chromium through frontend/scripts/browser-test.mjs,
# then stops what it started. Ports 8000 and 3000, as `make dev` has them. Never reads .env.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# An empty key in the environment wins over any key in a local .env: demo mode is forced.
export ANTHROPIC_API_KEY="" EVENT_SOURCE=file BACKEND_URL=http://127.0.0.1:8000
ADMIN_TOKEN="$(openssl rand -hex 24)"
export ADMIN_TOKEN

logs="$(mktemp -d)"
pids=()
stop() {
  status=$?
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] || continue
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
  done
  [ "$status" -eq 0 ] || tail -n 20 "$logs"/*.log >&2 2>/dev/null || true
  rm -rf "$logs"
  exit "$status"
}
trap stop INT TERM EXIT

(cd "$ROOT/backend" && exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000) >"$logs/backend.log" 2>&1 &
pids+=($!)
(cd "$ROOT/frontend" && exec npx next dev --port 3000) >"$logs/frontend.log" 2>&1 &
pids+=($!)

wait_for() {
  for _ in $(seq 1 120); do
    curl -fsS -o /dev/null --max-time 5 "$1" 2>/dev/null && return 0
    sleep 1
  done
  echo "browser-test: $1 did not answer within two minutes" >&2
  return 1
}
wait_for http://127.0.0.1:8000/health
wait_for http://localhost:3000/about

cd "$ROOT/frontend"
node scripts/browser-test.mjs
