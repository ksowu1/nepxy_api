<#
Usage:
  .\scripts\db_backup_staging.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$appName = "nepxy-staging"

function Require-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "Missing required command: $name"
        exit 2
    }
}

function Get-MachineId([string]$AppName) {
    try {
        $json = & fly machine list -a $AppName --json 2>$null
        if ($LASTEXITCODE -eq 0 -and $json) {
            $machines = $json | ConvertFrom-Json
            if ($machines -and $machines.Count -gt 0) {
                return $machines[0].id
            }
        }
    } catch {
        # fall through to text parsing
    }

    $lines = & fly machine list -a $AppName 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $lines) {
        throw "Unable to list Fly machines for $AppName."
    }
    foreach ($line in ($lines -split "`n")) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed -match "^ID\\s") { continue }
        $parts = $trimmed -split "\\s+"
        if ($parts.Count -gt 0) {
            return $parts[0]
        }
    }
    throw "No Fly machines found for $AppName."
}

Require-Command "fly"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backupDir = Join-Path $repoRoot "backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $backupDir ("staging-db-" + $stamp + ".sql")

$machineId = Get-MachineId $appName
Write-Host "Creating staging DB backup..."

$cmd = 'sh -lc "pg_dump \"$DATABASE_URL\""'
& fly ssh console --app $appName --machine $machineId -C $cmd > $backupFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backup failed. Ensure pg_dump is available in the Fly app image."
    exit 1
}

if (-not (Test-Path $backupFile) -or (Get-Item $backupFile).Length -eq 0) {
    Write-Error "Backup file is empty: $backupFile"
    exit 1
}

Write-Host ("Backup saved to " + $backupFile)
