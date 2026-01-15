Param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

Write-Host "WARNING: This will restore over the target database."
if ($env:DATABASE_URL) {
    Write-Host ("Target DATABASE_URL={0}" -f (Redact-DbUrl $env:DATABASE_URL))
} else {
    Write-Host ("Target PGHOST={0} PGUSER={1} PGDATABASE={2}" -f $env:PGHOST, $env:PGUSER, $env:PGDATABASE)
}

$confirm = Read-Host "Type RESTORE to continue"
if ($confirm -ne "RESTORE") {
    Write-Host "Aborted."
    exit 1
}

if ($env:DATABASE_URL) {
    & pg_restore --clean --if-exists --no-owner --no-privileges --dbname=$env:DATABASE_URL $BackupFile
} else {
    & pg_restore --clean --if-exists --no-owner --no-privileges $BackupFile
}

Write-Host "Restore completed."
