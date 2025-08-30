#!/usr/bin/env bash
set -euo pipefail

function cleanup {
  if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    kill "$UVICORN_PID"
  fi
}
trap cleanup EXIT

ruff check key_gen.py
pytest

uvicorn main:app --host 0.0.0.0 --port 5000 &
UVICORN_PID=$!
# Wait for server to start
sleep 3

curl -f http://localhost:5000/health
