# Usage:
#   .\scripts\db_backup.ps1 -AppName nepxy-staging -OutputFile .\backup.dump [-DatabaseUrl "..."]

param(
    [string]$AppName = "nepxy-staging",
    [string]$OutputFile = ".\\backup.dump",
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

Require-Command "pg_dump"
Require-Command "fly"

$dbUrl = $DatabaseUrl
if (-not $dbUrl) {
    $dbUrl = $env:DATABASE_URL
}
if (-not $dbUrl) {
    throw "DATABASE_URL not provided. Pass -DatabaseUrl or set `$env:DATABASE_URL."
}

Write-Host ("Running pg_dump against {0}" -f (Mask-DbUrl $dbUrl))
& pg_dump --format=custom --file=$OutputFile $dbUrl

Write-Host ("Backup saved to {0}" -f $OutputFile)
