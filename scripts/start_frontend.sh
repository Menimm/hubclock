#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT/frontend"

ENV_FILE="$PROJECT_ROOT/frontend/.env"
if [[ -f "$ENV_FILE" ]]; then
  set +u
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  set -u
fi

DEV_PORT="${VITE_DEV_PORT:-5173}"
DEV_HOST="${VITE_DEV_HOST:-127.0.0.1}"

npm run dev -- --host "$DEV_HOST" --port "$DEV_PORT"
