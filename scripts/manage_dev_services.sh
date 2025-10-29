#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-status}
BACKEND_SERVICE=hubclock-backend.service
FRONTEND_SERVICE=hubclock-frontend.service
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

mkdir -p "$RUN_DIR"

have_systemctl=false
if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files | grep -q "^${BACKEND_SERVICE}"; then
    have_systemctl=true
  fi
fi

start_process() {
  local script_path=$1
  local pid_file=$2
  local log_file=$3

  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[i] Process $(basename "$pid_file" .pid) already running (PID $pid)"
      return 0
    fi
    rm -f "$pid_file"
  fi

  nohup setsid bash "$script_path" >"$log_file" 2>&1 &
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "[i] Started $(basename "$pid_file" .pid) (PID $pid, logs: $log_file)"
}

stop_process() {
  local pid_file=$1
  if [[ ! -f "$pid_file" ]]; then
    echo "[i] $(basename "$pid_file" .pid) not running"
    return 0
  fi
  local pid
  pid=$(cat "$pid_file")
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo "[i] Stopped $(basename "$pid_file" .pid)"
  else
    echo "[i] $(basename "$pid_file" .pid) already stopped"
  fi
  rm -f "$pid_file"
}

status_process() {
  local name=$1
  local pid_file=$2
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$name: running (PID $pid)"
      return
    fi
  fi
  echo "$name: stopped"
}

case "$ACTION" in
  start)
    if [[ $have_systemctl == true ]]; then
      sudo systemctl start "$BACKEND_SERVICE"
      sudo systemctl start "$FRONTEND_SERVICE"
    else
      start_process "$PROJECT_ROOT/scripts/start_backend.sh" "$BACKEND_PID_FILE" "$BACKEND_LOG"
      start_process "$PROJECT_ROOT/scripts/start_frontend.sh" "$FRONTEND_PID_FILE" "$FRONTEND_LOG"
    fi
    ;;
  stop)
    if [[ $have_systemctl == true ]]; then
      sudo systemctl stop "$FRONTEND_SERVICE"
      sudo systemctl stop "$BACKEND_SERVICE"
    else
      stop_process "$FRONTEND_PID_FILE"
      stop_process "$BACKEND_PID_FILE"
    fi
    ;;
  restart)
    if [[ $have_systemctl == true ]]; then
      sudo systemctl restart "$BACKEND_SERVICE"
      sudo systemctl restart "$FRONTEND_SERVICE"
    else
      stop_process "$FRONTEND_PID_FILE"
      stop_process "$BACKEND_PID_FILE"
      start_process "$PROJECT_ROOT/scripts/start_backend.sh" "$BACKEND_PID_FILE" "$BACKEND_LOG"
      start_process "$PROJECT_ROOT/scripts/start_frontend.sh" "$FRONTEND_PID_FILE" "$FRONTEND_LOG"
    fi
    ;;
  status)
    if [[ $have_systemctl == true ]]; then
      sudo systemctl status "$BACKEND_SERVICE" || true
      echo
      sudo systemctl status "$FRONTEND_SERVICE" || true
    else
      status_process "backend" "$BACKEND_PID_FILE"
      status_process "frontend" "$FRONTEND_PID_FILE"
      echo "Logs:"
      echo "  backend -> $BACKEND_LOG"
      echo "  frontend -> $FRONTEND_LOG"
    fi
    ;;
  *)
    cat <<USAGE
Usage: ./scripts/manage_dev_services.sh [start|stop|restart|status]
Manages both hubclock-backend.service and hubclock-frontend.service together.
Falls back to background processes if systemd is unavailable.
USAGE
    exit 1
    ;;
esac
