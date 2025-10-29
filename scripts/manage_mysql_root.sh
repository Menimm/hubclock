#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-status}
DATA_DIR=${MYSQL_DATA_DIR:-/var/lib/mysql}
SOCKET=${MYSQL_SOCKET:-/var/run/mysqld/mysqld.sock}
LOG_FILE=${MYSQL_LOG_FILE:-/var/log/mysqld-root.log}
PID_FILE=${MYSQL_PID_FILE:-/var/run/hubclock-mysqld.pid}
BIND_ADDRESS=${MYSQL_BIND_ADDRESS:-0.0.0.0}
PORT=${MYSQL_PORT:-3306}

if [[ $EUID -ne 0 ]]; then
  echo "[!] This helper should be run as root (it starts mysqld directly)." >&2
  exit 1
fi

ensure_paths() {
  install -d -m 755 "$(dirname "$SOCKET")"
  touch "$LOG_FILE"
  chmod 600 "$LOG_FILE"
}

start_mysql() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(cat "$PID_FILE")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[i] mysqld already running (PID $pid)"
      return 0
    fi
    rm -f "$PID_FILE"
  fi

  ensure_paths

  local cmd=()
  if command -v mysqld_safe >/dev/null 2>&1; then
    cmd=(mysqld_safe --user=root --datadir="$DATA_DIR" --socket="$SOCKET" --port="$PORT" --bind-address="$BIND_ADDRESS" --skip-syslog)
  else
    cmd=(mysqld --user=root --datadir="$DATA_DIR" --socket="$SOCKET" --port="$PORT" --bind-address="$BIND_ADDRESS" --skip-syslog)
  fi

  echo "[i] Starting mysqld as root (logs: $LOG_FILE)"
  nohup "${cmd[@]}" >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 2
  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[i] mysqld started (PID $(cat "$PID_FILE"))"
  else
    echo "[!] mysqld failed to start. Check $LOG_FILE for details." >&2
    rm -f "$PID_FILE"
    exit 1
  fi
}

stop_mysql() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "[i] mysqld not running"
    return 0
  fi
  local pid
  pid=$(cat "$PID_FILE")
  if [[ -z "$pid" ]]; then
    rm -f "$PID_FILE"
    echo "[i] mysqld not running"
    return 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "[i] mysqld not running"
    return 0
  fi
  echo "[i] Stopping mysqld (PID $pid)"
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "[i] mysqld stopped"
}

status_mysql() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(cat "$PID_FILE")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "mysqld: running (PID $pid, socket $SOCKET)"
      return
    fi
  fi
  echo "mysqld: stopped"
}

case "$ACTION" in
  start)
    start_mysql
    ;;
  stop)
    stop_mysql
    ;;
  restart)
    stop_mysql
    start_mysql
    ;;
  status)
    status_mysql
    ;;
  *)
    cat <<USAGE
Usage: sudo ./scripts/manage_mysql_root.sh [start|stop|restart|status]
Uses mysqld_safe/mysqld directly so the server can run as root in constrained environments.
Environment overrides:
  MYSQL_DATA_DIR     (default /var/lib/mysql)
  MYSQL_SOCKET       (default /var/run/mysqld/mysqld.sock)
  MYSQL_PORT         (default 3306)
  MYSQL_BIND_ADDRESS (default 0.0.0.0)
  MYSQL_LOG_FILE     (default /var/log/mysqld-root.log)
  MYSQL_PID_FILE     (default /var/run/hubclock-mysqld.pid)
USAGE
    exit 1
    ;;
esac
