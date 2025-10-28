#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT"

source backend/.venv/bin/activate

export PYTHONPATH="$PROJECT_ROOT/backend"

exec uvicorn app.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000
