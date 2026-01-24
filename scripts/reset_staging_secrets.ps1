# Usage:
#   .\scripts\reset_staging_secrets.ps1 [-AppName nepxy-staging] [-RunCanary] [-SkipRestart]

param(
    [string]$AppName = "nepxy-staging",
    [bool]$RunCanary = $true,
    [bool]$SkipRestart = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "fly"
Require-Command "python"

$stagingGateKey = python -c "import secrets; print(secrets.token_urlsafe(48))"
$tmoneyWebhookSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
$userPassword = python -c "import secrets; print(secrets.token_urlsafe(18))"
$adminPassword = python -c "import secrets; print(secrets.token_urlsafe(18))"

Write-Host "Generated secrets (lengths only):"
Write-Host ("  STAGING_GATE_KEY length={0}" -f $stagingGateKey.Length)
Write-Host ("  TMONEY_WEBHOOK_SECRET length={0}" -f $tmoneyWebhookSecret.Length)
Write-Host ("  USER_PASSWORD length={0}" -f $userPassword.Length)
Write-Host ("  ADMIN_PASSWORD length={0}" -f $adminPassword.Length)

$secretArgs = @(
    "STAGING_GATE_KEY=$stagingGateKey",
    "TMONEY_WEBHOOK_SECRET=$tmoneyWebhookSecret",
    "USER_PASSWORD=$userPassword",
    "ADMIN_PASSWORD=$adminPassword"
)

& fly secrets set @secretArgs -a $AppName

if (-not $SkipRestart) {
    & fly machine restart -a $AppName
}

$envSync = Join-Path $PSScriptRoot "_env_staging_from_fly.ps1"
if (Test-Path $envSync) {
    . $envSync
}

if ($RunCanary) {
    if ($env:BOOTSTRAP_ADMIN_SECRET) {
        $env:CANARY_ALLOW_BOOTSTRAP = "1"
    }
    & python scripts/canary_smoke.py
}
