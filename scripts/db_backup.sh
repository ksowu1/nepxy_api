#!/usr/bin/env bash
set -euo pipefail

out_dir="backups"
mkdir -p "$out_dir"

timestamp="$(date -u +%Y%m%d_%H%M%S)"
git_sha="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [[ -z "$git_sha" ]]; then
  git_sha="nogit"
fi

outfile="${out_dir}/nepxy_backup_${timestamp}_${git_sha}.dump"

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

db_url="${DATABASE_URL:-${FLY_DATABASE_URL:-}}"
if [[ -n "$db_url" ]]; then
  echo "Using DB URL: $(redact_url "$db_url")"
  pg_dump --format=custom --file="$outfile" "$db_url"
else
  echo "Using PGHOST=${PGHOST:-} PGUSER=${PGUSER:-} PGDATABASE=${PGDATABASE:-}"
  pg_dump --format=custom --file="$outfile"
fi

if [[ ! -s "$outfile" ]]; then
  echo "Backup failed or empty: $outfile" >&2
  exit 1
fi

echo "Backup written: $outfile"
echo "Restore command:"
echo "  scripts/db_restore.sh --i-know-what-im-doing \"$outfile\""
