#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[!] Run this script with sudo (it installs system packages)." >&2
  exit 1
fi

PROJECT_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
APP_USER=${SUDO_USER:-$(whoami)}

export DEBIAN_FRONTEND=noninteractive

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

apt update
apt install -y python3 python3-venv python3-pip nodejs npm

INSTALL_MYSQL=true
if command -v mysql >/dev/null 2>&1; then
  read -rp "MySQL appears to be installed already. Re-install/ensure service? [y/N] " REINSTALL_MYSQL
  if [[ ! ${REINSTALL_MYSQL:-N} =~ ^[Yy]$ ]]; then
    INSTALL_MYSQL=false
  fi
else
  read -rp "Install MySQL Server locally (recommended)? [Y/n] " INSTALL_MYSQL_PROMPT
  if [[ ${INSTALL_MYSQL_PROMPT:-Y} =~ ^[Nn]$ ]]; then
    INSTALL_MYSQL=false
  fi
fi

if [[ $INSTALL_MYSQL == true ]]; then
  apt install -y mysql-server
  if systemctl list-unit-files | grep -q "^mysql.service"; then
    systemctl enable --now mysql
  else
    echo "[!] Unable to locate mysql.service after installation. Please start MySQL manually." >&2
  fi
else
  echo "[i] Skipping MySQL installation. Ensure an accessible MySQL instance is available."
fi

cd "$PROJECT_ROOT"
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

deactivate

npm_config_cache="$PROJECT_ROOT/.cache/npm" npm install --prefix frontend

BACKEND_ENV="$PROJECT_ROOT/backend/.env"
FRONTEND_ENV="$PROJECT_ROOT/frontend/.env"

if [[ ! -f "$BACKEND_ENV" ]]; then
  cp "$PROJECT_ROOT/backend/.env.example" "$BACKEND_ENV"
  echo "[i] Created backend/.env from template."
fi

if [[ ! -f "$FRONTEND_ENV" ]]; then
  cp "$PROJECT_ROOT/frontend/.env.example" "$FRONTEND_ENV"
  echo "[i] Created frontend/.env from template."
fi

backend_host_default=$(get_env_value "UVICORN_HOST" "$BACKEND_ENV")
backend_host_default=${backend_host_default:-127.0.0.1}
read -rp "Backend bind host [$backend_host_default]: " backend_host
backend_host=${backend_host:-$backend_host_default}
set_env_value "$BACKEND_ENV" "UVICORN_HOST" "$backend_host"

backend_port_default=$(get_env_value "UVICORN_PORT" "$BACKEND_ENV")
backend_port_default=${backend_port_default:-8000}
read -rp "Backend bind port [$backend_port_default]: " backend_port
backend_port=${backend_port:-$backend_port_default}
set_env_value "$BACKEND_ENV" "UVICORN_PORT" "$backend_port"

frontend_api_default=$(get_env_value "VITE_API_BASE_URL" "$FRONTEND_ENV")
frontend_api_default=${frontend_api_default:-http://127.0.0.1:8000}
read -rp "Backend API base URL for the frontend [$frontend_api_default]: " frontend_api
frontend_api=${frontend_api:-$frontend_api_default}
set_env_value "$FRONTEND_ENV" "VITE_API_BASE_URL" "$frontend_api"

frontend_port_default=$(get_env_value "VITE_DEV_PORT" "$FRONTEND_ENV")
frontend_port_default=${frontend_port_default:-5173}
read -rp "Frontend dev server port [$frontend_port_default]: " frontend_port
frontend_port=${frontend_port:-$frontend_port_default}
set_env_value "$FRONTEND_ENV" "VITE_DEV_PORT" "$frontend_port"

echo
echo "Saved configuration:"
echo "  backend/.env -> UVICORN_HOST=$backend_host, UVICORN_PORT=$backend_port"
echo "  frontend/.env -> VITE_API_BASE_URL=$frontend_api, VITE_DEV_PORT=$frontend_port"

if command -v mysql >/dev/null 2>&1; then
  read -rp "Create default HubClock database and user now? [y/N] " CREATE_DB
  if [[ ${CREATE_DB:-N} =~ ^[Yy]$ ]]; then
    mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS hubclock CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'hubclock'@'localhost' IDENTIFIED BY 'hubclock';
GRANT ALL PRIVILEGES ON hubclock.* TO 'hubclock'@'localhost';
FLUSH PRIVILEGES;
SQL
    echo "[i] Database 'hubclock' and user 'hubclock' provisioned."
  else
    echo "[i] Skipping database creation. You can run mysql commands later."
  fi
else
  cat <<'MYSQL_NOTE'
[!] MySQL client not available. Skipped database/user creation.
    Install MySQL (e.g., sudo apt install mysql-server) or point the application to a remote instance.
MYSQL_NOTE
fi

cat <<INSTRUCTIONS
HubClock setup complete.

Next steps:
  - Consider running 'sudo mysql_secure_installation' to harden MySQL if it is installed locally.
  - Configure backend credentials in backend/.env if you change defaults.
  - Generate schema once:
       PYTHONPATH=$PROJECT_ROOT/backend $PROJECT_ROOT/backend/.venv/bin/uvicorn app.main:app --host $backend_host --port $backend_port
       curl -X POST http://127.0.0.1:$backend_port/db/init
  - Frontend dev server listens on port $frontend_port (from frontend/.env).
    Run it with: npm run dev -- --host 127.0.0.1 --port $frontend_port
INSTRUCTIONS
