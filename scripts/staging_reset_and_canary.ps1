# scripts/staging_reset_and_canary.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_env_staging_from_fly.ps1")

$env:CANARY_ALLOW_BOOTSTRAP = "1"

$baseUrl = $env:STAGING_BASE_URL
if (-not $baseUrl) {
    Write-Host "Missing STAGING_BASE_URL after loading env." -ForegroundColor Red
    exit 1
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
    } else {
        throw
    }
}

python scripts/canary_smoke.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Canary smoke failed." -ForegroundColor Red
    exit $LASTEXITCODE
}
