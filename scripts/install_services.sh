#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[!] Run this script with sudo (it installs systemd units)." >&2
  exit 1
fi

PROJECT_ROOT=$(cd "$(dirname "$0")"/.. && pwd)
APP_USER=${SUDO_USER:-$(whoami)}
SERVICE_DIR=/etc/systemd/system

render_service() {
  local template=$1
  local output=$2
  sed "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g; s|{{USER}}|$APP_USER|g" "$template" > "$output"
}

render_service "$PROJECT_ROOT/deploy/hubclock-backend.service" /tmp/hubclock-backend.service
render_service "$PROJECT_ROOT/deploy/hubclock-frontend.service" /tmp/hubclock-frontend.service

mv /tmp/hubclock-backend.service "$SERVICE_DIR/hubclock-backend.service"
mv /tmp/hubclock-frontend.service "$SERVICE_DIR/hubclock-frontend.service"

systemctl daemon-reload
systemctl enable hubclock-backend.service
systemctl enable hubclock-frontend.service

cat <<MSG
Services installed. Use:
  sudo systemctl start hubclock-backend.service
  sudo systemctl start hubclock-frontend.service

To check status:
  sudo systemctl status hubclock-backend.service
  sudo systemctl status hubclock-frontend.service
MSG
