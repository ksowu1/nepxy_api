<#
Usage:
  .\scripts\release_staging.ps1
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

Require-Command "fly"
Require-Command "python"

Write-Host "Deploying to Fly ($appName)..."
& fly deploy --app $appName --remote-only

Write-Host "Loading staging env from Fly..."
. (Join-Path $PSScriptRoot "_env_staging_from_fly.ps1")
$env:CANARY_ALLOW_BOOTSTRAP = "1"

Write-Host "Running staging canary..."
& python scripts/canary_smoke.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Canary failed. Rollback instructions:"
    Write-Host ("  fly releases -a " + $appName)
    Write-Host ("  fly releases revert <RELEASE_ID> -a " + $appName)
    exit $LASTEXITCODE
}

Write-Host "Staging release OK."
