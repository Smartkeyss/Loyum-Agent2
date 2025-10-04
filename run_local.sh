#!/usr/bin/env bash
set -euo pipefail

# always run from the script's directory = project root
cd "$(dirname "$0")"

# .env must exist and be unix-formatted
if [ ! -f .env ]; then
  echo "No .env file found. Create one from .env.example before running." >&2
  exit 1
fi

# normalize CRLF if the file was edited on Windows
if file -b .env | grep -qi 'CRLF'; then dos2unix .env; fi

# export env vars (simple KEY=VALUE per line; comments allowed)
export $(grep -v '^[[:space:]]*#' .env | grep -v '^[[:space:]]*$' | xargs -d '\n')

# make Python see the project root as a package source
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

# start backend
python3 -m uvicorn app.backend.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

# start frontend
python3 -m streamlit run app/frontend/streamlit_app.py

