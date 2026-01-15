Param(
    [string]$OutDir = "backups"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$outfile = Join-Path $OutDir ("nepxy_backup_{0}.dump" -f $timestamp)

function Redact-DbUrl([string]$Url) {
    if ($Url -match "^(?<scheme>[^:]+)://(?<user>[^:]+):(?<pass>[^@]+)@(?<rest>.+)$") {
        return ("{0}://{1}:[REDACTED]@{2}" -f $Matches.scheme, $Matches.user, $Matches.rest)
    }
    return $Url
}

if ($env:DATABASE_URL) {
    Write-Host ("Using DATABASE_URL={0}" -f (Redact-DbUrl $env:DATABASE_URL))
    & pg_dump --format=custom --file="$outfile" $env:DATABASE_URL
} else {
    Write-Host ("Using PGHOST={0} PGUSER={1} PGDATABASE={2}" -f $env:PGHOST, $env:PGUSER, $env:PGDATABASE)
    & pg_dump --format=custom --file="$outfile"
}

Write-Host ("Backup written: {0}" -f $outfile)
