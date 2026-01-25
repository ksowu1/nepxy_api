#!/usr/bin/env bash
set -euo pipefail

if [[ "${ENV:-}" == "production" && "${ALLOW_PROD_RESTORE:-}" != "1" ]]; then
  echo "Refusing to restore in production without ALLOW_PROD_RESTORE=1." >&2
  exit 1
fi

confirm=false
backup_file=""
for arg in "$@"; do
  case "$arg" in
    --i-know-what-im-doing)
      confirm=true
      ;;
    *)
      backup_file="$arg"
      ;;
  esac
done

if [[ "$confirm" != "true" ]]; then
  echo "Usage: scripts/db_restore.sh --i-know-what-im-doing <backup-file>" >&2
  exit 2
fi

if [[ -z "$backup_file" ]]; then
  echo "Backup file is required." >&2
  exit 2
fi

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file" >&2
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

db_url="${DATABASE_URL:-${FLY_DATABASE_URL:-}}"
echo "WARNING: This will restore over the target database."
if [[ -n "$db_url" ]]; then
  echo "Target DB URL: $(redact_url "$db_url")"
else
  echo "Target PGHOST=${PGHOST:-} PGUSER=${PGUSER:-} PGDATABASE=${PGDATABASE:-}"
fi

if [[ -n "$db_url" ]]; then
  pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$db_url" "$backup_file"
else
  pg_restore --clean --if-exists --no-owner --no-privileges "$backup_file"
fi

echo "Restore completed."
echo "Post-restore checklist:"
echo "  - Run scripts/db_validate.sh to verify counts and alembic revision"
echo "  - Validate recent payout, webhook, and ledger activity in the app"
