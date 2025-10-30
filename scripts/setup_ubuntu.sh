#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[!] Run this script with sudo (it installs system packages)." >&2
  exit 1
fi

PROJECT_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
APP_USER=${SUDO_USER:-$(whoami)}
if [[ $APP_USER == "root" ]]; then
  echo "[i] Running as root: backend and frontend services will run as root (container-friendly)." >&2
fi

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
  echo "[i] Detected IPv4 addresses: ${IPV4_CANDIDATES[*]}"
fi

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
  DB_SERVICE_STARTED=false
  if ! apt install -y mysql-server; then
    echo "[!] mysql-server package unavailable. Attempting to install default-mysql-server instead." >&2
    apt install -y default-mysql-server
  fi
  start_service() {
    local svc=$1
    if command -v systemctl >/dev/null 2>&1; then
      if systemctl list-unit-files | grep -q "^${svc}.service"; then
        if systemctl enable --now "$svc"; then
          DB_SERVICE_STARTED=true
        else
          echo "[!] systemctl failed to start ${svc}. Attempting with 'service'." >&2
          if service "$svc" start; then
            DB_SERVICE_STARTED=true
          else
            echo "[!] Please start ${svc} manually." >&2
          fi
        fi
        return
      fi
    fi
    if command -v service >/dev/null 2>&1; then
      if service "$svc" start; then
        DB_SERVICE_STARTED=true
      else
        echo "[!] Please start ${svc} manually." >&2
      fi
    else
      echo "[!] Unable to control ${svc} (systemctl/service unavailable). Start it manually." >&2
    fi
  }

  if systemctl list-unit-files | grep -q "^mysql.service"; then
    start_service mysql
  elif systemctl list-unit-files | grep -q "^mariadb.service"; then
    start_service mariadb
  else
    echo "[!] Unable to locate mysql.service or mariadb.service after installation. Please start MySQL manually." >&2
  fi
  if [[ $DB_SERVICE_STARTED == false ]]; then
    cat <<'MYSQL_MANUAL'
[!] MySQL/MariaDB service did not start automatically.
    In constrained environments (containers without full systemd privileges) you can launch the daemon manually:
        sudo ./scripts/manage_mysql_root.sh start
    The helper starts mysqld directly as root and logs to /var/log/mysqld-root.log.
MYSQL_MANUAL
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
if [[ -z "$backend_host_default" || "$backend_host_default" == "127.0.0.1" ]]; then
  if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
    backend_host_default=${IPV4_CANDIDATES[0]}
  else
    backend_host_default=127.0.0.1
  fi
fi
read -rp "Backend bind host [$backend_host_default]: " backend_host
backend_host=${backend_host:-$backend_host_default}
set_env_value "$BACKEND_ENV" "UVICORN_HOST" "$backend_host"

backend_port_default=$(get_env_value "UVICORN_PORT" "$BACKEND_ENV")
backend_port_default=${backend_port_default:-8000}
read -rp "Backend bind port [$backend_port_default]: " backend_port
backend_port=${backend_port:-$backend_port_default}
set_env_value "$BACKEND_ENV" "UVICORN_PORT" "$backend_port"

frontend_api_default=$(get_env_value "VITE_API_BASE_URL" "$FRONTEND_ENV")
if [[ -z "$frontend_api_default" || "$frontend_api_default" == http://127.0.0.1:8000 ]]; then
  if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
    frontend_api_default="http://${IPV4_CANDIDATES[0]}:$backend_port/api"
  else
    frontend_api_default="http://127.0.0.1:$backend_port/api"
  fi
fi
read -rp "Backend API base URL for the frontend [$frontend_api_default]: " frontend_api
frontend_api=${frontend_api:-$frontend_api_default}
set_env_value "$FRONTEND_ENV" "VITE_API_BASE_URL" "$frontend_api"

frontend_host_default=$(get_env_value "VITE_DEV_HOST" "$FRONTEND_ENV")
if [[ -z "$frontend_host_default" || "$frontend_host_default" == 127.0.0.1 ]]; then
  if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
    frontend_host_default=${IPV4_CANDIDATES[0]}
  else
    frontend_host_default=127.0.0.1
  fi
fi
read -rp "Frontend dev server host [$frontend_host_default]: " frontend_host
frontend_host=${frontend_host:-$frontend_host_default}
set_env_value "$FRONTEND_ENV" "VITE_DEV_HOST" "$frontend_host"

frontend_port_default=$(get_env_value "VITE_DEV_PORT" "$FRONTEND_ENV")
frontend_port_default=${frontend_port_default:-5173}
read -rp "Frontend dev server port [$frontend_port_default]: " frontend_port
frontend_port=${frontend_port:-$frontend_port_default}
set_env_value "$FRONTEND_ENV" "VITE_DEV_PORT" "$frontend_port"

echo
echo "Saved configuration:"
echo "  backend/.env -> UVICORN_HOST=$backend_host, UVICORN_PORT=$backend_port"
echo "  frontend/.env -> VITE_API_BASE_URL=$frontend_api, VITE_DEV_HOST=$frontend_host, VITE_DEV_PORT=$frontend_port"

read -rp "Build frontend production bundle now? [y/N] " BUILD_BUNDLE
if [[ ${BUILD_BUNDLE:-N} =~ ^[Yy]$ ]]; then
  echo "[i] Building frontend production bundle..."
  npm --prefix "$PROJECT_ROOT/frontend" run build
  echo "[✓] frontend/dist refreshed."
fi

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

services_started=false
read -rp "Start HubClock dev services now? [y/N] " START_SERVICES
if [[ ${START_SERVICES:-N} =~ ^[Yy]$ ]]; then
  set +e
  "$PROJECT_ROOT/scripts/manage_dev_services.sh" start
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    services_started=true
    echo "[i] Services started. Use ./scripts/manage_dev_services.sh status for details."
  else
    echo "[!] Failed to start services automatically. See logs under $PROJECT_ROOT/.run/."
  fi
fi

test_host=$backend_host
if [[ "$test_host" == "0.0.0.0" || "$test_host" == "127.0.0.1" ]]; then
  if [[ ${#IPV4_CANDIDATES[@]} -gt 0 ]]; then
    test_host=${IPV4_CANDIDATES[0]}
  else
    test_host=127.0.0.1
  fi
fi

read -rp "Test admin PIN verification endpoint at http://$test_host:$backend_port/api/auth/verify-pin now? [y/N] " TEST_PIN
if [[ ${TEST_PIN:-N} =~ ^[Yy]$ ]]; then
  read -rsp "Enter PIN to test (input hidden): " PIN_INPUT
  echo
  tmp_response=$(mktemp)
  set +e
  http_status=$(curl -sS -o "$tmp_response" -w "%{http_code}" \
    -X POST "http://$test_host:$backend_port/api/auth/verify-pin" \
    -H "Content-Type: application/json" \
    -d "{\"pin\":\"$PIN_INPUT\"}")
  curl_rc=$?
  set -e
  if [[ $curl_rc -ne 0 ]]; then
    echo "[!] curl failed (backend may be offline): see output below."
  else
    if [[ $http_status -eq 200 ]]; then
      echo "[✓] PIN verified successfully."
    else
      echo "[i] Endpoint responded with HTTP $http_status: $(cat "$tmp_response")"
    fi
  fi
  rm -f "$tmp_response"
fi

INSTALL_NGINX=false
read -rp "Install and configure Nginx reverse proxy on port 80? [y/N] " INSTALL_NGINX_CHOICE
if [[ ${INSTALL_NGINX_CHOICE:-N} =~ ^[Yy]$ ]]; then
  INSTALL_NGINX=true
  apt install -y nginx

  server_name_default=$(hostname -f 2>/dev/null || echo "_")
  read -rp "Hostname for Nginx server_name [$server_name_default]: " nginx_server_name
  nginx_server_name=${nginx_server_name:-$server_name_default}

  nginx_listen_default=80
  read -rp "Public HTTP port Nginx should listen on [$nginx_listen_default]: " nginx_listen
  nginx_listen=${nginx_listen:-$nginx_listen_default}

  nginx_conf_path=/etc/nginx/sites-available/hubclock.conf
  cat >"$nginx_conf_path" <<NGINX_CONF
server {
    listen ${nginx_listen};
    server_name ${nginx_server_name};

    client_max_body_size 16m;

    location /api/ {
        proxy_pass http://127.0.0.1:${backend_port}/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }

    location / {
        proxy_pass http://127.0.0.1:${backend_port}/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
NGINX_CONF

  ln -sf "$nginx_conf_path" /etc/nginx/sites-enabled/hubclock.conf
  if [[ -f /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
  fi
  systemctl reload nginx
  echo "[i] Nginx configured. Requests to http://${nginx_server_name}:${nginx_listen} proxy to backend on ${backend_port}."

  read -rp "Switch to production backend service (serves frontend/dist) behind Nginx? [y/N] " ENABLE_PROD
  if [[ ${ENABLE_PROD:-N} =~ ^[Yy]$ ]]; then
    if [[ $services_started == true ]]; then
      set +e
      "$PROJECT_ROOT/scripts/manage_dev_services.sh" stop
      set -e
      services_started=false
    fi
    "$PROJECT_ROOT/scripts/install_services.sh" --production
    systemctl restart hubclock-backend.service
    echo "[i] Production backend is running. Access the app via http://${nginx_server_name}:${nginx_listen}/"
  fi

  read -rp "Request Let's Encrypt SSL certificates with certbot now? [y/N] " ENABLE_CERTBOT
  if [[ ${ENABLE_CERTBOT:-N} =~ ^[Yy]$ ]]; then
    if [[ "$nginx_listen" != "80" ]]; then
      echo "[!] Let's Encrypt HTTP-01 validation requires port 80. Temporarily binding 80 for validation."
      sed -i "s/listen ${nginx_listen};/listen 80;/" "$nginx_conf_path"
      systemctl reload nginx
    fi
    apt install -y certbot python3-certbot-nginx
    echo "[i] Certbot will reconfigure Nginx for HTTPS. Ensure DNS for ${nginx_server_name} points to this server."
    certbot --nginx -d "$nginx_server_name"
    https_port_default=443
    read -rp "HTTPS port to serve traffic on after certificate issuance [${https_port_default}]: " nginx_https_port
    nginx_https_port=${nginx_https_port:-$https_port_default}
    if [[ "$nginx_https_port" != "443" ]]; then
      sed -i "s/listen 443 ssl;/listen ${nginx_https_port} ssl;/" "$nginx_conf_path"
      sed -i "s/listen \[::\]:443 ssl;/listen [::]:${nginx_https_port} ssl;/" "$nginx_conf_path" || true
    fi
    if [[ "$nginx_listen" != "80" ]]; then
      sed -i "s/listen 80;/listen ${nginx_listen};/" "$nginx_conf_path"
    fi
    systemctl reload nginx
    echo "[i] Certbot finished. Certificates stored under /etc/letsencrypt/live/${nginx_server_name}/. HTTPS listens on ${nginx_https_port}."
  fi
fi

cat <<INSTRUCTIONS
HubClock setup complete.

Next steps:
  - Consider running 'sudo mysql_secure_installation' to harden MySQL if it is installed locally.
  - Configure backend credentials in backend/.env if you change defaults.
  - Generate schema once:
       PYTHONPATH=$PROJECT_ROOT/backend $PROJECT_ROOT/backend/.venv/bin/uvicorn app.main:app --host $backend_host --port $backend_port
      curl -X POST http://127.0.0.1:$backend_port/api/db/init
  - Frontend dev server listens on port $frontend_port (from frontend/.env).
    Run it with: npm run dev -- --host 127.0.0.1 --port $frontend_port
INSTRUCTIONS
