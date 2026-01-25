Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    Write-Error "psql is required for validation."
    exit 1
}

if (-not (Get-Command alembic -ErrorAction SilentlyContinue)) {
    Write-Error "alembic is required for validation."
    exit 1
}

$dbUrl = $env:DATABASE_URL
if (-not $dbUrl) {
    $dbUrl = $env:FLY_DATABASE_URL
}

if (-not $dbUrl) {
    Write-Error "DATABASE_URL (or FLY_DATABASE_URL) is required."
    exit 2
}

Write-Host "Running row counts..."
& psql $dbUrl -v ON_ERROR_STOP=1 -c @"
select 'users.users' as table, count(*) as rows from users.users
union all select 'ledger.wallet_balances', count(*) from ledger.wallet_balances
union all select 'ledger.ledger_entries', count(*) from ledger.ledger_entries
union all select 'app.mobile_money_payouts', count(*) from app.mobile_money_payouts
union all select 'app.webhook_events', count(*) from app.webhook_events
order by table;
"@

Write-Host "Checking alembic revision..."
$headRev = (& alembic heads -q | Select-Object -First 1).Trim()
$dbRev = (& psql $dbUrl -tA -c "select version_num from alembic_version").Trim()

if (-not $dbRev) {
    Write-Error "alembic_version table is empty or missing."
    exit 1
}

if ($dbRev -ne $headRev) {
    Write-Error ("alembic_version ({0}) does not match head ({1})" -f $dbRev, $headRev)
    exit 1
}

Write-Host ("Alembic revision OK: {0}" -f $dbRev)
