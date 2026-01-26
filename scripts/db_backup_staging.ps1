<#
Usage:
  .\scripts\db_backup_staging.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

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
$errFile = Join-Path $env:TEMP ("fly-ssh-" + $stamp + ".err")

$machineId = Get-MachineId $appName
Write-Host "Creating staging DB backup..."

& {
    $oldEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & fly machine start $machineId -a $appName | Out-Null
    $ErrorActionPreference = $oldEa
}
Start-Sleep -Seconds 2

$ensureCmd = "sh -lc 'command -v pg_dump >/dev/null 2>&1 || (apt-get update && apt-get install -y postgresql-client)'"
& {
    $oldEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & fly ssh console --pty=false --app $appName --machine $machineId -C $ensureCmd 2> $errFile | Out-Null
    $ErrorActionPreference = $oldEa
}
if (Test-Path $errFile) { Remove-Item $errFile -ErrorAction SilentlyContinue }

$cmd = 'sh -lc ''pg_dump "$DATABASE_URL"'''
& {
    $oldEa = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & fly ssh console --pty=false --app $appName --machine $machineId -C $cmd 2> $errFile > $backupFile
    $ErrorActionPreference = $oldEa
}
$exitCode = $LASTEXITCODE
$backupOk = (Test-Path $backupFile) -and (Get-Item $backupFile).Length -gt 0
$errText = ""
if (Test-Path $errFile) {
    $errRaw = Get-Content $errFile -Raw
    if ($errRaw) {
        $errText = $errRaw.Trim()
    }
}
if (-not $backupOk) {
    if ($errText) {
        Write-Error ("Backup failed: " + $errText)
    } else {
        Write-Error "Backup failed. Ensure pg_dump is available in the Fly app image."
    }
    exit 1
}
if ($exitCode -ne 0 -and $errText -and $errText -notmatch "The handle is invalid") {
    Write-Warning ("Non-fatal SSH output: " + $errText)
}
if (-not $backupOk) {
    Write-Error "Backup file is empty: $backupFile"
    exit 1
}

$size = (Get-Item $backupFile).Length
Write-Host ("Backup saved to " + $backupFile + " (" + $size + " bytes)")
