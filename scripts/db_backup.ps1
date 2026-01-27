Param(
    [string]$OutDir = "backups"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$gitSha = (& git rev-parse --short HEAD 2>$null)
if (-not $gitSha) {
    $gitSha = "nogit"
}

$outfile = Join-Path $OutDir ("nepxy_backup_{0}_{1}.dump" -f $timestamp, $gitSha.Trim())

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

if ($dbUrl) {
    Write-Host ("Using DB URL: {0}" -f (Redact-DbUrl $dbUrl))
    & pg_dump --format=custom --file="$outfile" $dbUrl
} else {
    Write-Host ("Using PGHOST={0} PGUSER={1} PGDATABASE={2}" -f $env:PGHOST, $env:PGUSER, $env:PGDATABASE)
    & pg_dump --format=custom --file="$outfile"
}

$fileInfo = Get-Item $outfile
if ($fileInfo.Length -le 0) {
    Write-Error ("Backup failed or empty: {0}" -f $outfile)
    exit 1
}

Write-Host ("Backup written: {0}" -f $outfile)
Write-Host "Restore command:"
Write-Host ("  scripts\db_restore.ps1 -BackupFile ""{0}"" -Iknowwhatimdoing" -f $outfile)
