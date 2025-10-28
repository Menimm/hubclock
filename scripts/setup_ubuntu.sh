#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[!] Run this script with sudo (it installs system packages)." >&2
  exit 1
fi

PROJECT_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
APP_USER=${SUDO_USER:-$(whoami)}

export DEBIAN_FRONTEND=noninteractive

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
       PYTHONPATH=$PROJECT_ROOT/backend $PROJECT_ROOT/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
       curl -X POST http://127.0.0.1:8000/db/init
INSTRUCTIONS
