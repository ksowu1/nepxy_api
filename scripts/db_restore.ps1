Param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [switch]$Iknowwhatimdoing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:ENV -eq "production" -and $env:ALLOW_PROD_RESTORE -ne "1") {
    Write-Error "Refusing to restore in production without ALLOW_PROD_RESTORE=1."
    exit 1
}

if (-not $Iknowwhatimdoing) {
    Write-Error "Usage: scripts\db_restore.ps1 -BackupFile <file> -Iknowwhatimdoing"
    exit 2
}

if (-not (Test-Path $BackupFile)) {
    Write-Error ("Backup file not found: {0}" -f $BackupFile)
    exit 2
}

function Redact-DbUrl([string]$Url) {
    if ($Url -match "^(?<scheme>[^:]+)://(?<user>[^:]+):(?<pass>[^@]+)@(?<rest>.+)$") {
        return ("{0}://{1}:[REDACTED]@{2}" -f $Matches.scheme, $Matches.user, $Matches.rest)
    }
    return $Url
}

$dbUrl = $env:DATABASE_URL
if (-not $dbUrl) {
    $dbUrl = $env:FLY_DATABASE_URL
}

Write-Host "WARNING: This will restore over the target database."
if ($dbUrl) {
    Write-Host ("Target DB URL: {0}" -f (Redact-DbUrl $dbUrl))
} else {
    Write-Host ("Target PGHOST={0} PGUSER={1} PGDATABASE={2}" -f $env:PGHOST, $env:PGUSER, $env:PGDATABASE)
}

if ($dbUrl) {
    & pg_restore --clean --if-exists --no-owner --no-privileges --dbname=$dbUrl $BackupFile
} else {
    & pg_restore --clean --if-exists --no-owner --no-privileges $BackupFile
}

Write-Host "Restore completed."
Write-Host "Post-restore checklist:"
Write-Host "  - Run scripts\db_validate.ps1 to verify counts and alembic revision"
Write-Host "  - Validate recent payout, webhook, and ledger activity in the app"
