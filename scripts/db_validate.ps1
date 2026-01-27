Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Load-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) {
        return $false
    }
    $raw = Get-Content -Path $Path -Raw
    if (-not $raw) {
        return $false
    }
    $loaded = $false
    foreach ($line in ($raw -split "`n")) {
        $trim = $line.Trim()
        if (-not $trim -or $trim.StartsWith("#")) { continue }
        if ($trim -match "^\s*export\s+") {
            $trim = $trim -replace "^\s*export\s+", ""
        }
        $idx = $trim.IndexOf("=")
        if ($idx -lt 1) { continue }
        $name = $trim.Substring(0, $idx).Trim()
        $value = $trim.Substring($idx + 1).Trim()
        if (-not $name) { continue }
        if ($value -match '^(\".*\"|''.*'')$') {
            $value = $value.Substring(1, $value.Length - 2)
        } else {
            $value = ($value -replace "\s+#.*$", "").Trim()
        }
        if (-not (Get-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue)) {
            Set-Item -Path ("Env:" + $name) -Value $value
            $loaded = $true
        }
    }
    return $loaded
}

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
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
    $envPath = Join-Path $repoRoot ".env"
    Load-DotEnv $envPath | Out-Null
    $dbUrl = $env:DATABASE_URL
    if (-not $dbUrl) {
        $dbUrl = $env:FLY_DATABASE_URL
    }
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
order by 1;
"@
if ($LASTEXITCODE -ne 0) {
    Write-Error "Row count query failed. Check DATABASE_URL connectivity."
    exit 1
}

Write-Host "Checking alembic revision..."
$headRevOutput = $null
$headExit = 1
try {
    $headRevOutput = & alembic heads -q 2>$null
    $headExit = $LASTEXITCODE
} catch {
    $headExit = 1
}
if ($headExit -ne 0 -or -not $headRevOutput) {
    try {
        $headRevOutput = & alembic heads 2>$null
        $headExit = $LASTEXITCODE
    } catch {
        $headExit = 1
    }
}
if ($headExit -ne 0 -or -not $headRevOutput) {
    Write-Error "Failed to read alembic heads."
    exit 1
}
$headRevLine = ($headRevOutput | Select-Object -First 1).Trim()
$headRev = $headRevLine
if ($headRevLine -match "^([0-9a-z_]+)") {
    $headRev = $Matches[1]
}

$dbRev = (& psql $dbUrl -tA -c "select version_num from alembic_version").Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to read alembic_version from DATABASE_URL."
    exit 1
}

if (-not $dbRev) {
    Write-Error "alembic_version table is empty or missing."
    exit 1
}

if ($dbRev -ne $headRev) {
    Write-Error ("alembic_version ({0}) does not match head ({1})" -f $dbRev, $headRev)
    exit 1
}

Write-Host ("Alembic revision OK: {0}" -f $dbRev)
