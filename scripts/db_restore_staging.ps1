<#
Usage:
  $env:CONFIRM_RESTORE="YES"
  .\scripts\db_restore_staging.ps1 -BackupFile .\backups\staging-db-YYYYMMDD-HHMMSS.sql
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

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

if ($env:CONFIRM_RESTORE -ne "YES") {
    Write-Error "Refusing to restore. Set CONFIRM_RESTORE=YES to continue."
    exit 2
}

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 2
}

Write-Host "============================================================"
Write-Host "WARNING: This will overwrite staging data."
Write-Host "Backup file: $BackupFile"
Write-Host "============================================================"

$machineId = Get-MachineId $appName
$cmd = 'sh -lc "psql \"$DATABASE_URL\""'

Get-Content -Raw $BackupFile | & fly ssh console --app $appName --machine $machineId -C $cmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Restore failed."
    exit 1
}

Write-Host "Restore completed."
