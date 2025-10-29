#!/usr/bin/env bash
set -euo pipefail

MODE="dev"
if [[ ${1:-} == "--production" ]]; then
  MODE="prod"
fi

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

HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-8000}"
WORKERS="${UVICORN_WORKERS:-4}"

COMMON_ARGS=(
  app.main:app
  --host "$HOST"
  --port "$PORT"
)

if [[ $MODE == "prod" ]]; then
  exec uvicorn "${COMMON_ARGS[@]}" --workers "$WORKERS" --proxy-headers --forwarded-allow-ips="*"
else
  exec uvicorn "${COMMON_ARGS[@]}"
fi
