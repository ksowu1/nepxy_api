# Usage:
#   .\scripts\db_restore.ps1 -AppName nepxy-staging -InputFile .\backup.dump [-DatabaseUrl "..."]

param(
    [string]$AppName = "nepxy-staging",
    [string]$InputFile = ".\\backup.dump",
    [string]$DatabaseUrl = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Mask-DbUrl([string]$Value) {
    if (-not $Value) { return "<empty>" }
    return ($Value -replace ":(//)?[^@]+@", "://***@")
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "pg_restore"
Require-Command "fly"

if (-not (Test-Path $InputFile)) {
    throw "Input file not found: $InputFile"
}

$dbUrl = $DatabaseUrl
if (-not $dbUrl) {
    $dbUrl = $env:DATABASE_URL
}
if (-not $dbUrl) {
    throw "DATABASE_URL not provided. Pass -DatabaseUrl or set `$env:DATABASE_URL."
}

Write-Host ("Running pg_restore against {0}" -f (Mask-DbUrl $dbUrl))
& pg_restore --clean --if-exists --no-owner --no-privileges --dbname=$dbUrl $InputFile

Write-Host "Restore completed."
