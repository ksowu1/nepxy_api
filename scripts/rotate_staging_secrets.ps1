# scripts/rotate_staging_secrets.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-Secret([int]$Bytes) {
    $cmd = "import secrets; print(secrets.token_urlsafe($Bytes))"
    $value = & python -c $cmd
    if (-not $value) {
        throw "Failed to generate secret via python."
    }
    return $value.Trim()
}

$stagingGateKey = New-Secret 48
$tmoneySecret = New-Secret 48
$userPassword = New-Secret 18
$adminPassword = New-Secret 18

& fly secrets set `
    STAGING_GATE_KEY="$stagingGateKey" `
    TMONEY_WEBHOOK_SECRET="$tmoneySecret" `
    USER_PASSWORD="$userPassword" `
    ADMIN_PASSWORD="$adminPassword" `
    -a nepxy-staging

if ($LASTEXITCODE -ne 0) {
    throw "fly secrets set failed."
}

& fly machine restart --app nepxy-staging
if ($LASTEXITCODE -ne 0) {
    throw "fly machine restart failed."
}

. (Join-Path $PSScriptRoot "_env_staging_from_fly.ps1")

$baseUrl = $env:STAGING_BASE_URL
if (-not $baseUrl) {
    throw "Missing STAGING_BASE_URL after loading env."
}

$headers = @{
    "X-Staging-Key" = $env:STAGING_GATE_KEY
    "X-Bootstrap-Admin-Secret" = $env:BOOTSTRAP_ADMIN_SECRET
}

try {
    Invoke-RestMethod -Method Post -Uri "$baseUrl/debug/bootstrap-staging-users" -Headers $headers | Out-Null
    Write-Host "Bootstrap staging users ok."
} catch {
    $resp = $_.Exception.Response
    if ($resp -and $resp.StatusCode.value__ -eq 404) {
        Write-Host "Bootstrap endpoint not available; skipping."
    } elseif ($resp -and $resp.StatusCode.value__ -eq 403) {
        Write-Host "Bootstrap failed: bad secret." -ForegroundColor Red
        exit 1
    } else {
        throw
    }
}

python scripts/canary_smoke.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Canary smoke failed." -ForegroundColor Red
    exit $LASTEXITCODE
}
