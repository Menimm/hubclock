#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo "[!] Run this script with sudo (it installs systemd units)." >&2
  exit 1
fi

MODE="dev"
ACTION="install"
if [[ $# -gt 0 ]]; then
  case "$1" in
    --prod|--production)
      MODE="prod"
      ;;
    --dev|--development)
      MODE="dev"
      ;;
    --remove-prod|--remove-production)
      ACTION="remove_prod"
      ;;
    --remove-dev|--remove-development)
      ACTION="remove_dev"
      ;;
    --help|-h)
      cat <<USAGE
Usage: sudo ./scripts/install_services.sh [--production|--dev|--remove-production|--remove-development]

Options:
  --production         Install production unit(s) (backend only, serves built frontend assets)
  --dev                Install development units (backend + Vite dev server)
  --remove-production  Stop, disable, and remove production service(s)
  --remove-development Stop, disable, and remove development service(s)
USAGE
      exit 0
      ;;
    *)
      echo "[!] Unknown option: $1" >&2
      exit 1
      ;;
  esac
fi

PROJECT_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
APP_USER=${SUDO_USER:-$(whoami)}
if [[ $APP_USER == "root" ]]; then
  echo "[i] Installing services to run as root." >&2
fi
SERVICE_DIR=/etc/systemd/system

render_service() {
  local template=$1
  local output=$2
  sed "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g; s|{{USER}}|$APP_USER|g" "$template" > "$output"
}

install_backend_service() {
  local template=$1
  render_service "$template" /tmp/hubclock-backend.service
  mv /tmp/hubclock-backend.service "$SERVICE_DIR/hubclock-backend.service"
}

install_frontend_service() {
  local template=$1
  render_service "$template" /tmp/hubclock-frontend.service
  mv /tmp/hubclock-frontend.service "$SERVICE_DIR/hubclock-frontend.service"
}

remove_service() {
  local unit=$1
  if systemctl list-unit-files | grep -q "^${unit}.service"; then
    systemctl stop "${unit}.service" || true
    systemctl disable "${unit}.service" || true
    rm -f "$SERVICE_DIR/${unit}.service"
    echo "[i] Removed ${unit}.service"
  fi
}

if [[ $ACTION == "remove_prod" ]]; then
  remove_service "hubclock-backend"
  systemctl daemon-reload
  echo "[i] Production services removed."
  exit 0
elif [[ $ACTION == "remove_dev" ]]; then
  remove_service "hubclock-frontend"
  remove_service "hubclock-backend"
  systemctl daemon-reload
  echo "[i] Development services removed."
  exit 0
fi

if [[ $MODE == "prod" ]]; then
  echo "[i] Preparing production deployment"
  install_backend_service "$PROJECT_ROOT/deploy/hubclock-backend-prod.service"

  echo "[i] Building frontend static assets"
  npm --prefix "$PROJECT_ROOT/frontend" install --prefer-offline >/dev/null
  npm --prefix "$PROJECT_ROOT/frontend" run build

  if systemctl list-units --full -all | grep -q "hubclock-frontend.service"; then
    systemctl stop hubclock-frontend.service || true
    systemctl disable hubclock-frontend.service || true
    rm -f "$SERVICE_DIR/hubclock-frontend.service"
  fi

  systemctl daemon-reload
  systemctl enable hubclock-backend.service

  cat <<MSG
[i] Production backend service installed.
Use:
  sudo systemctl start hubclock-backend.service

Frontend assets are served from frontend/dist by the backend.
MSG
else
  echo "[i] Installing development services"
  install_backend_service "$PROJECT_ROOT/deploy/hubclock-backend.service"
  install_frontend_service "$PROJECT_ROOT/deploy/hubclock-frontend.service"

  systemctl daemon-reload
  systemctl enable hubclock-backend.service
  systemctl enable hubclock-frontend.service

  cat <<MSG
[i] Development services installed. Use:
  sudo systemctl start hubclock-backend.service
  sudo systemctl start hubclock-frontend.service

To check status:
  sudo systemctl status hubclock-backend.service
  sudo systemctl status hubclock-frontend.service
MSG
fi
