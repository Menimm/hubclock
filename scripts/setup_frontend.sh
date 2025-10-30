#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT/frontend"

CACHE_DIR="$PROJECT_ROOT/.cache/npm"
mkdir -p "$CACHE_DIR"
RUN_DIR="$PROJECT_ROOT/.run"
mkdir -p "$RUN_DIR"

npm_config_cache="$CACHE_DIR" npm install

detect_ipv4_candidates() {
  local -a addrs=()
  if command -v ip >/dev/null 2>&1; then
    while IFS= read -r addr; do
      [[ -n "$addr" ]] && addrs+=("$addr")
    done < <(ip -o -4 addr show scope global up | awk '{print $4}' | cut -d/ -f1)
  fi
  if [[ ${#addrs[@]} -eq 0 ]] && command -v hostname >/dev/null 2>&1; then
    for addr in $(hostname -I 2>/dev/null); do
      [[ -n "$addr" && "$addr" != "127.0.0.1" ]] && addrs+=("$addr")
    done
  fi
  printf '%s\n' "${addrs[@]}"
}

mapfile -t IPV4_CANDIDATES < <(detect_ipv4_candidates)
if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
  echo "[i] Detected IPv4 addresses on this host: ${IPV4_CANDIDATES[*]}"
fi

ENV_FILE="$PROJECT_ROOT/frontend/.env"
ENV_TEMPLATE="$PROJECT_ROOT/frontend/.env.example"

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

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  echo "[i] Created frontend/.env from template."
fi

default_port=$(get_env_value "VITE_DEV_PORT" "$ENV_FILE")
default_port=${default_port:-5173}

default_api=$(get_env_value "VITE_API_BASE_URL" "$ENV_FILE")
if [[ -z "$default_api" || "$default_api" == http://127.0.0.1:8000 ]]; then
  if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
    default_api="http://${IPV4_CANDIDATES[0]}:8000/api"
  else
    default_api="http://127.0.0.1:8000/api"
  fi
fi
echo "[?] Which URL should the browser use for API calls (VITE_API_BASE_URL)?"
echo "    Use http://<this-machine-ip>:<backend-port>/api when the frontend is accessed remotely."
read -rp "Backend API base URL [$default_api]: " api_base
api_base=${api_base:-$default_api}
set_env_value "$ENV_FILE" "VITE_API_BASE_URL" "$api_base"

read -rp "Frontend dev server port [$default_port]: " dev_port
dev_port=${dev_port:-$default_port}
set_env_value "$ENV_FILE" "VITE_DEV_PORT" "$dev_port"

echo
echo "Frontend configuration saved to frontend/.env:"
echo "  VITE_API_BASE_URL=$api_base"
echo "  VITE_DEV_PORT=$dev_port"

echo "Frontend dependencies installed. Start dev server with: npm run dev"

read -rp "Start frontend dev server now? [y/N] " START_FRONTEND
if [[ ${START_FRONTEND:-N} =~ ^[Yy]$ ]]; then
  FRONTEND_LOG="$RUN_DIR/frontend.log"
  echo "[i] Launching frontend dev server in background (logs: $FRONTEND_LOG)"
  set +e
  nohup bash "$PROJECT_ROOT/scripts/start_frontend.sh" >"$FRONTEND_LOG" 2>&1 &
  pid=$!
  set -e
  echo "$pid" >"$RUN_DIR/frontend.pid"
  echo "[✓] Frontend dev server started (PID $pid)."
fi
