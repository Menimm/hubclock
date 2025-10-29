#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT"

source backend/.venv/bin/activate

export PYTHONPATH="$PROJECT_ROOT/backend"

ENV_FILE="$PROJECT_ROOT/backend/.env"
if [[ -f "$ENV_FILE" ]]; then
  set +u
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  set -u
fi

HOST="${UVICORN_HOST:-127.0.0.1}"
PORT="${UVICORN_PORT:-8000}"

exec uvicorn app.main:app \
  --reload \
  --host "$HOST" \
  --port "$PORT"
