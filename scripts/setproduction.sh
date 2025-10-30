#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: sudo ./scripts/setproduction.sh <command> [component ...]

Commands:
  install     Install and enable selected component services (default: all)
  uninstall   Stop/disable selected component services and remove configs
  start       Start selected component services (default: all)
  stop        Stop selected component services (default: all)
  status      Show status for selected component services (default: all)
  help        Show this message

Components:
  backend     Production FastAPI service (hubclock-backend.service)
  nginx       Nginx reverse proxy (hubclock site config)
  mysql       MySQL/MariaDB database service (if installed)
  all         Apply to every component (default when none specified)

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

ensure_components() {
  local parsed=()
  if [[ $# -eq 0 ]]; then
    parsed=(backend nginx mysql)
  else
    for item in "$@"; do
      case "$item" in
        all)
          parsed=(backend nginx mysql)
          echo "${parsed[@]}"
          return
          ;;
        backend|nginx|mysql)
          parsed+=("$item")
          ;;
        *)
          echo "[!] Unknown component: $item" >&2
          exit 1
          ;;
      esac
    done
  fi
  if [[ ${#parsed[@]} -eq 0 ]]; then
    parsed=(backend nginx mysql)
  fi
  echo "${parsed[@]}"
}

install_backend() { ./scripts/install_services.sh --production; }
install_nginx()   { start_service nginx; }
install_mysql()   { start_service mysql || start_service mariadb || true; }

uninstall_backend() { ./scripts/install_services.sh --remove-production; }
uninstall_nginx() {
  systemctl stop nginx || true
  systemctl disable nginx || true
  rm -f /etc/nginx/sites-enabled/hubclock.conf /etc/nginx/sites-available/hubclock.conf || true
}
uninstall_mysql() { echo "[i] Skipping MySQL removal. Manage it manually if desired."; }

start_backend() { start_service hubclock-backend; }
start_nginx()   { start_service nginx; }
start_mysql()   { start_service mysql || start_service mariadb || true; }

stop_backend() { stop_service hubclock-backend; }
stop_nginx()   { stop_service nginx; }
stop_mysql()   { echo "[i] Leaving MySQL running. Use systemctl stop mysql if needed."; }

status_backend() { systemctl status hubclock-backend.service || true; }
status_nginx()   { systemctl status nginx.service || true; }
status_mysql() {
  if service_exists mysql; then
    systemctl status mysql.service || true
  elif service_exists mariadb; then
    systemctl status mariadb.service || true
  else
    echo "[i] MySQL/MariaDB service not installed"
  fi
}

run_install() {
  need_root
  read -r -a components <<<"$(ensure_components "${@:2}")"
  for comp in "${components[@]}"; do
    echo "[i] Installing $comp"
    case "$comp" in
      backend) install_backend ;;
      nginx)   install_nginx   ;;
      mysql)   install_mysql   ;;
    esac
  done
  systemctl daemon-reload
  echo "[✓] Install complete"
}

run_uninstall() {
  need_root
  read -r -a components <<<"$(ensure_components "${@:2}")"
  for comp in "${components[@]}"; do
    echo "[i] Uninstalling $comp"
    case "$comp" in
      backend) uninstall_backend ;;
      nginx)   uninstall_nginx   ;;
      mysql)   uninstall_mysql   ;;
    esac
  done
  systemctl daemon-reload
  echo "[✓] Uninstall complete"
}

run_start() {
  need_root
  read -r -a components <<<"$(ensure_components "${@:2}")"
  for comp in "${components[@]}"; do
    echo "[i] Starting $comp"
    case "$comp" in
      backend) start_backend ;;
      nginx)   start_nginx   ;;
      mysql)   start_mysql   ;;
    esac
  done
  echo "[✓] Start complete"
}

run_stop() {
  need_root
  read -r -a components <<<"$(ensure_components "${@:2}")"
  for comp in "${components[@]}"; do
    echo "[i] Stopping $comp"
    case "$comp" in
      backend) stop_backend ;;
      nginx)   stop_nginx   ;;
      mysql)   stop_mysql   ;;
    esac
  done
}

run_status() {
  read -r -a components <<<"$(ensure_components "${@:2}")"
  for comp in "${components[@]}"; do
    echo "=== ${comp^^} ==="
    case "$comp" in
      backend) status_backend ;;
      nginx)   status_nginx   ;;
      mysql)   status_mysql   ;;
    esac
    echo
  done
}

main() {
  local cmd=${1:-help}
  case "$cmd" in
    install)
      run_install "$@"
      ;;
    uninstall)
      run_uninstall "$@"
      ;;
    start)
      run_start "$@"
      ;;
    stop)
      run_stop "$@"
      ;;
    status)
      run_status "$@"
      ;;
    help)
      usage
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
