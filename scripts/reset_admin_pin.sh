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

SETTINGS_ID="$(mysql "${MYSQL_OPTS[@]}" -e "SELECT id FROM settings ORDER BY id LIMIT 1;")" || {
  log ERROR "Unable to read settings table"
  unset MYSQL_PWD
  exit 1
}

if [[ -z "$SETTINGS_ID" ]]; then
  log ERROR "No settings row found. Initialise the application before attempting a PIN reset."
  unset MYSQL_PWD
  exit 1
fi

log INFO "Updating PIN hash for settings row id=${SETTINGS_ID}"
mysql "${MYSQL_OPTS[@]}" -e "UPDATE settings SET pin_hash='${PIN_HASH}' WHERE id=${SETTINGS_ID};" || {
  log ERROR "Failed to update PIN hash"
  unset MYSQL_PWD
  exit 1
}

unset MYSQL_PWD
log INFO "Admin PIN updated successfully"
