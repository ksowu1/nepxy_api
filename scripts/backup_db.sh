#!/usr/bin/env bash
set -euo pipefail

mkdir -p backups

timestamp="$(date -u +%Y%m%d_%H%M%S)"
outfile="backups/nepxy_backup_${timestamp}.dump"

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

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "Using DATABASE_URL=$(redact_url "$DATABASE_URL")"
  pg_dump --format=custom --file="$outfile" "$DATABASE_URL"
else
  echo "Using PGHOST=${PGHOST:-} PGUSER=${PGUSER:-} PGDATABASE=${PGDATABASE:-}"
  pg_dump --format=custom --file="$outfile"
fi

echo "Backup written: $outfile"
