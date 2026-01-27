# Usage:
#   .\scripts\rotate_secrets_staging.ps1
# Examples:
#   .\scripts\rotate_secrets_staging.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$appName = "nepxy-staging"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Mask-Value([string]$Value) {
    if (-not $Value) { return "<empty>" }
    if ($Value.Length -le 4) { return ("*" * $Value.Length) }
    return ("*" * ($Value.Length - 4)) + $Value.Substring($Value.Length - 4)
}

Require-Command "fly"
Require-Command "python"

$stagingGateKey = python -c "import secrets; print(secrets.token_urlsafe(48))"
$tmoneyWebhookSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
$thunesWebhookSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
$bootstrapSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
$userPassword = python -c "import secrets; print(secrets.token_urlsafe(18))"
$adminPassword = python -c "import secrets; print(secrets.token_urlsafe(18))"

Write-Host "Generated secrets (masked):"
Write-Host ("  STAGING_GATE_KEY=" + (Mask-Value $stagingGateKey))
Write-Host ("  TMONEY_WEBHOOK_SECRET=" + (Mask-Value $tmoneyWebhookSecret))
Write-Host ("  THUNES_WEBHOOK_SECRET=" + (Mask-Value $thunesWebhookSecret))
Write-Host ("  BOOTSTRAP_ADMIN_SECRET=" + (Mask-Value $bootstrapSecret))
Write-Host ("  USER_PASSWORD=" + (Mask-Value $userPassword))
Write-Host ("  ADMIN_PASSWORD=" + (Mask-Value $adminPassword))

$secretArgs = @(
    "STAGING_GATE_KEY=$stagingGateKey",
    "TMONEY_WEBHOOK_SECRET=$tmoneyWebhookSecret",
    "THUNES_WEBHOOK_SECRET=$thunesWebhookSecret",
    "BOOTSTRAP_ADMIN_SECRET=$bootstrapSecret",
    "USER_PASSWORD=$userPassword",
    "ADMIN_PASSWORD=$adminPassword"
)

& fly secrets set @secretArgs -a $appName
& fly machine restart -a $appName

. $PSScriptRoot\_env_staging_from_fly.ps1

$env:STAGING_GATE_KEY = $stagingGateKey
$env:TMONEY_WEBHOOK_SECRET = $tmoneyWebhookSecret
$env:THUNES_WEBHOOK_SECRET = $thunesWebhookSecret
$env:BOOTSTRAP_ADMIN_SECRET = $bootstrapSecret
$env:STAGING_USER_PASSWORD = $userPassword
$env:STAGING_ADMIN_PASSWORD = $adminPassword
$env:USER_PASSWORD = $userPassword
$env:ADMIN_PASSWORD = $adminPassword
$env:CANARY_ALLOW_BOOTSTRAP = "1"

$baseUrl = $env:STAGING_BASE_URL
if (-not $baseUrl) {
    $baseUrl = "https://nepxy-staging.fly.dev"
}

$headers = @{ "X-Staging-Key" = $env:STAGING_GATE_KEY }
Invoke-RestMethod "$baseUrl/health" -Headers $headers | Out-Null

& python scripts/canary_smoke.py
