# Usage:
#   .\scripts\staging_recover.ps1
# Examples:
#   .\scripts\staging_recover.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$appName = "nepxy-staging"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "fly"
Require-Command "python"

. $PSScriptRoot\_env_staging_from_fly.ps1
$env:CANARY_ALLOW_BOOTSTRAP = "1"

& fly machine restart -a $appName

$canaryExit = 0
try {
    & python scripts/canary_smoke.py
    $canaryExit = $LASTEXITCODE
} catch {
    $canaryExit = 1
}

if ($canaryExit -ne 0) {
    Write-Host "Canary failed. Check recent Fly logs and OpenAPI routes." -ForegroundColor Yellow
    Write-Host "Logs: flyctl logs --app $appName --since 10m"
    Write-Host "OpenAPI: curl -sS $($env:STAGING_BASE_URL)/openapi.json | rg '\"/debug/|\"/v1/'"
    exit $canaryExit
}

Write-Host "Staging recovery completed successfully."
