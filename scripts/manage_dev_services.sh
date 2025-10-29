#!/usr/bin/env bash
set -euo pipefail

ACTION=${1:-status}
BACKEND_SERVICE=hubclock-backend.service
FRONTEND_SERVICE=hubclock-frontend.service

case "$ACTION" in
  start)
    sudo systemctl start "$BACKEND_SERVICE"
    sudo systemctl start "$FRONTEND_SERVICE"
    ;;
  stop)
    sudo systemctl stop "$FRONTEND_SERVICE"
    sudo systemctl stop "$BACKEND_SERVICE"
    ;;
  restart)
    sudo systemctl restart "$BACKEND_SERVICE"
    sudo systemctl restart "$FRONTEND_SERVICE"
    ;;
  status)
    sudo systemctl status "$BACKEND_SERVICE"
    echo
    sudo systemctl status "$FRONTEND_SERVICE"
    ;;
  *)
    cat <<USAGE
Usage: ./scripts/manage_dev_services.sh [start|stop|restart|status]
Manages both hubclock-backend.service and hubclock-frontend.service together.
USAGE
    exit 1
    ;;
esac
