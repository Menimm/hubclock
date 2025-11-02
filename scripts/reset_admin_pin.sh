#!/usr/bin/env bash
# Emergency HubClock admin PIN reset utility.
# Usage: bash scripts/reset_admin_pin.sh
# The script reads MySQL connection details from the environment (or an .env file)
# and updates the existing settings row with a freshly generated bcrypt hash.

set -euo pipefail

log() {
  local level="$1"; shift
  printf '%s %-5s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$level" "$*" >&2
}

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
  log INFO "Loading environment overrides from ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
else
  log INFO "Environment file ${ENV_FILE} not found; relying on current environment or defaults"
fi

MYSQL_USER="${MYSQL_USER:-hubclock}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-hubclock}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-hubclock}"

if ! command -v mysql >/dev/null 2>&1; then
  log ERROR "mysql client not found in PATH"
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  log ERROR "openssl not found in PATH"
  exit 1
fi

read_secure_pin() {
  local prompt="$1"
  local pin
  read -r -s -p "$prompt" pin
  printf '%s' "$pin"
}

validate_pin() {
  local pin="$1"
  local length=${#pin}
  if (( length < 4 || length > 12 )); then
    log ERROR "PIN must be between 4 and 12 characters"
    exit 1
  fi
}

PIN="$(read_secure_pin "Enter new admin PIN: ")"
echo
PIN_CONFIRM="$(read_secure_pin "Confirm new admin PIN: ")"
echo

if [[ "$PIN" != "$PIN_CONFIRM" ]]; then
  log ERROR "PIN entries did not match"
  exit 1
fi

validate_pin "$PIN"

log INFO "Generating bcrypt hash (cost=12)"
PIN_HASH="$(printf '%s' "$PIN" | openssl passwd -bcrypt -cost 12 -stdin)"
unset PIN PIN_CONFIRM

if [[ -z "$PIN_HASH" ]]; then
  log ERROR "Failed to generate bcrypt hash"
  exit 1
fi

log INFO "Connecting to MySQL at ${MYSQL_HOST}:${MYSQL_PORT}/${MYSQL_DATABASE}"
export MYSQL_PWD="${MYSQL_PASSWORD}"

MYSQL_OPTS=(-u "$MYSQL_USER" -h "$MYSQL_HOST" -P "$MYSQL_PORT" -N -s "$MYSQL_DATABASE")

readarray -t ADMIN_ROWS < <(mysql "${MYSQL_OPTS[@]}" -e "SELECT id, name, active FROM admin_accounts ORDER BY name;") || {
  log ERROR "Unable to query admin accounts"
  unset MYSQL_PWD
  exit 1
}

TARGET_ID=""
TARGET_NAME=""

if (( ${#ADMIN_ROWS[@]} > 0 )); then
  log INFO "Existing admin accounts:"
  for row in "${ADMIN_ROWS[@]}"; do
    IFS=$'\t' read -r admin_id admin_name admin_active <<<"$row"
    printf '  [%s] %s (active=%s)\n' "$admin_id" "$admin_name" "$admin_active"
  done
  read -r -p "Enter admin ID to reset (leave blank to create new): " TARGET_ID
  if [[ -n "$TARGET_ID" ]]; then
    MATCH_ROW="$(mysql "${MYSQL_OPTS[@]}" -e "SELECT name FROM admin_accounts WHERE id=${TARGET_ID};")"
    if [[ -z "$MATCH_ROW" ]]; then
      log ERROR "Admin ID ${TARGET_ID} not found"
      unset MYSQL_PWD
      exit 1
    fi
    TARGET_NAME="$MATCH_ROW"
  fi
fi

if [[ -z "$TARGET_ID" ]]; then
  read -r -p "Enter name for the admin account: " TARGET_NAME
  if [[ -z "$TARGET_NAME" ]]; then
    log ERROR "Admin name cannot be empty"
    unset MYSQL_PWD
    exit 1
  fi
  ESCAPED_NAME="$(printf "%s" "$TARGET_NAME" | sed "s/'/''/g")"
  log INFO "Creating new admin account '${TARGET_NAME}'"
  mysql "${MYSQL_OPTS[@]}" -e "INSERT INTO admin_accounts (name, pin_hash, active, created_at, updated_at) VALUES ('${ESCAPED_NAME}', '${PIN_HASH}', 1, NOW(), NOW());" || {
    log ERROR "Failed to create admin account"
    unset MYSQL_PWD
    exit 1
  }
else
  log INFO "Updating PIN hash for admin '${TARGET_NAME}' (id=${TARGET_ID})"
  mysql "${MYSQL_OPTS[@]}" -e "UPDATE admin_accounts SET pin_hash='${PIN_HASH}', active=1, updated_at=NOW() WHERE id=${TARGET_ID};" || {
    log ERROR "Failed to update admin PIN"
    unset MYSQL_PWD
    exit 1
  }
fi

unset MYSQL_PWD
log INFO "Admin PIN updated successfully"
