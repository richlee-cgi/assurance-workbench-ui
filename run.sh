#!/usr/bin/env bash
set -euo pipefail

HOST="${ASSURANCE_WORKBENCH_UI_HOST:-127.0.0.1}"
PORT="${ASSURANCE_WORKBENCH_UI_PORT:-8765}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  printf 'ERROR: expected virtualenv Python at %s\n' "$PYTHON_BIN" >&2
  printf 'Run ./install.sh first, or create .venv and install the app manually.\n' >&2
  exit 1
fi

cd "$SCRIPT_DIR"
printf 'Starting Assure-O-Matic 3000 Workbench at http://%s:%s\n' "$HOST" "$PORT"
exec "$PYTHON_BIN" -m uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
