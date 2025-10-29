#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: sudo ./scripts/setproduction.sh <command>

Commands:
  install     Install and enable Nginx + production backend service
  uninstall   Stop and disable Nginx + production backend service
  start       Start Nginx, MySQL, and production backend service
  stop        Stop production backend service and Nginx (MySQL left untouched)
  status      Show status for production backend, Nginx, and MySQL

The script assumes \`scripts/setup_ubuntu.sh\` has already configured the environment.
USAGE
}

need_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "[!] Run this command with sudo." >&2
    exit 1
  fi
}

service_exists() {
  local svc=$1
  systemctl list-unit-files | grep -q "^${svc}.service"
}

start_service() {
  local svc=$1
  if service_exists "$svc"; then
    systemctl enable "$svc" >/dev/null
    systemctl start "$svc"
  fi
}

stop_service() {
  local svc=$1
  if service_exists "$svc"; then
    systemctl stop "$svc" || true
  fi
}

remove_service() {
  local svc=$1
  if service_exists "$svc"; then
    systemctl stop "$svc" || true
    systemctl disable "$svc" || true
    rm -f "/etc/systemd/system/${svc}.service"
  fi
}

install() {
  need_root
  echo "[i] Installing production backend service"
  ./scripts/install_services.sh --production
  echo "[i] Ensuring Nginx and MySQL are enabled"
  start_service nginx
  start_service mysql || start_service mariadb || true
  systemctl daemon-reload
  echo "[✓] Installation complete"
}

uninstall() {
  need_root
  echo "[i] Removing production backend service and Nginx site"
  ./scripts/install_services.sh --remove-production
  systemctl stop nginx || true
  systemctl disable nginx || true
  rm -f /etc/nginx/sites-enabled/hubclock.conf /etc/nginx/sites-available/hubclock.conf || true
  systemctl daemon-reload
  echo "[✓] Uninstall complete"
}

start_all() {
  need_root
  start_service mysql || start_service mariadb || true
  start_service nginx
  start_service hubclock-backend
  systemctl status hubclock-backend.service nginx.service mysql.service, mariadb.service >/dev/null 2>&1 || true
  echo "[✓] Services started"
}

stop_all() {
  need_root
  stop_service hubclock-backend
  stop_service nginx
  echo "[i] Production backend and Nginx stopped. MySQL left running."
}

show_status() {
  systemctl status hubclock-backend.service || true
  echo
  systemctl status nginx.service || true
  echo
  if service_exists mysql; then
    systemctl status mysql.service || true
  elif service_exists mariadb; then
    systemctl status mariadb.service || true
  else
    echo "[i] MySQL/MariaDB service not installed"
  fi
}

main() {
  local cmd=${1:-help}
  case "$cmd" in
    install)
      install
      ;;
    uninstall)
      uninstall
      ;;
    start)
      start_all
      ;;
    stop)
      stop_all
      ;;
    status)
      show_status
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
