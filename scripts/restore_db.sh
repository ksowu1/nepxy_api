#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/restore_db.sh <backup-file>"
  exit 2
fi

backup_file="$1"
if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file"
  exit 2
fi

redact_url() {
  local url="$1"
  if [[ "$url" == *"@"* && "$url" == *"://"* ]]; then
    local scheme="${url%%://*}"
    local rest="${url#*://}"
    local creds_and_host="${rest%%@*}"
    local host_and_path="${rest#*@}"
    if [[ "$creds_and_host" == *":"* ]]; then
      local user="${creds_and_host%%:*}"
      echo "${scheme}://${user}:[REDACTED]@${host_and_path}"
      return
    fi
  fi
  echo "$url"
}

echo "WARNING: This will restore over the target database."
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "Target DATABASE_URL=$(redact_url "$DATABASE_URL")"
else
  echo "Target PGHOST=${PGHOST:-} PGUSER=${PGUSER:-} PGDATABASE=${PGDATABASE:-}"
fi
read -r -p "Type RESTORE to continue: " confirm
if [[ "$confirm" != "RESTORE" ]]; then
  echo "Aborted."
  exit 1
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$DATABASE_URL" "$backup_file"
else
  pg_restore --clean --if-exists --no-owner --no-privileges "$backup_file"
fi

echo "Restore completed."
