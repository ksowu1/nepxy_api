#!/usr/bin/env bash
set -euo pipefail

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required for validation." >&2
  exit 1
fi

if ! command -v alembic >/dev/null 2>&1; then
  echo "alembic is required for validation." >&2
  exit 1
fi

db_url="${DATABASE_URL:-${FLY_DATABASE_URL:-}}"

if [[ -z "$db_url" ]]; then
  echo "DATABASE_URL (or FLY_DATABASE_URL) is required." >&2
  exit 2
fi

echo "Running row counts..."
psql "$db_url" -v ON_ERROR_STOP=1 -c "
select 'users.users' as table, count(*) as rows from users.users
union all select 'ledger.wallet_balances', count(*) from ledger.wallet_balances
union all select 'ledger.ledger_entries', count(*) from ledger.ledger_entries
union all select 'app.mobile_money_payouts', count(*) from app.mobile_money_payouts
union all select 'app.webhook_events', count(*) from app.webhook_events
order by table;"

echo "Checking alembic revision..."
head_rev="$(alembic heads -q | head -n 1)"
db_rev="$(psql "$db_url" -tA -c "select version_num from alembic_version")"
if [[ -z "$db_rev" ]]; then
  echo "alembic_version table is empty or missing." >&2
  exit 1
fi
if [[ "$db_rev" != "$head_rev" ]]; then
  echo "alembic_version ($db_rev) does not match head ($head_rev)" >&2
  exit 1
fi

echo "Alembic revision OK: $db_rev"
