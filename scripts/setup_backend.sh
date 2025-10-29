#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE="$PROJECT_ROOT/backend/.env"
ENV_TEMPLATE="$PROJECT_ROOT/backend/.env.example"
RUN_DIR="$PROJECT_ROOT/.run"
mkdir -p "$RUN_DIR"

get_env_value() {
  local key=$1
  local file=$2
  if [[ -f "$file" ]]; then
    awk -F= -v key="$key" '$1==key {print substr($0, index($0, "=")+1)}' "$file" | tail -n1
  fi
}

set_env_value() {
  local file=$1
  local key=$2
  local value=$3
  python3 - "$file" "$key" "$value" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

lines = []
if path.exists():
    lines = path.read_text().splitlines()

needle = f"{key}="
for index, line in enumerate(lines):
    if line.startswith(needle):
        lines[index] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n")
PY
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    echo "[i] Created backend/.env from template."
  fi
}

python3 -m venv backend/.venv
source backend/.venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

ensure_env_file

default_host=$(get_env_value "UVICORN_HOST" "$ENV_FILE")
default_host=${default_host:-127.0.0.1}
read -rp "Backend bind host [$default_host]: " backend_host
backend_host=${backend_host:-$default_host}
set_env_value "$ENV_FILE" "UVICORN_HOST" "$backend_host"

default_port=$(get_env_value "UVICORN_PORT" "$ENV_FILE")
default_port=${default_port:-8000}
read -rp "Backend bind port [$default_port]: " backend_port
backend_port=${backend_port:-$default_port}
set_env_value "$ENV_FILE" "UVICORN_PORT" "$backend_port"

echo
echo "Backend configuration saved to backend/.env:"
echo "  UVICORN_HOST=$backend_host"
echo "  UVICORN_PORT=$backend_port"

echo "Backend environment ready. Activate with: source backend/.venv/bin/activate"

read -rp "Start backend dev server now? [y/N] " START_BACKEND
if [[ ${START_BACKEND:-N} =~ ^[Yy]$ ]]; then
  BACKEND_LOG="$RUN_DIR/backend.log"
  echo "[i] Launching backend dev server in background (logs: $BACKEND_LOG)"
  set +e
  nohup bash "$PROJECT_ROOT/scripts/start_backend.sh" >"$BACKEND_LOG" 2>&1 &
  pid=$!
  set -e
  echo "$pid" >"$RUN_DIR/backend.pid"
  echo "[✓] Backend dev server started (PID $pid)."
fi
