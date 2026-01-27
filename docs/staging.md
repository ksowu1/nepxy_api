# Staging Guide

## Load staging env
```powershell
. .\scripts\_env_staging_from_fly.ps1
```

## Run canary with bootstrap allowed
```powershell
$env:CANARY_ALLOW_BOOTSTRAP="1"
python scripts\canary_smoke.py
```

## Rotate staging secrets
Rotate these keys: `STAGING_GATE_KEY`, `USER_PASSWORD`, `ADMIN_PASSWORD`, `TMONEY_WEBHOOK_SECRET`.

PowerShell example:
```powershell
flyctl secrets set `
  STAGING_GATE_KEY="REDACTED" `
  USER_PASSWORD="REDACTED" `
  ADMIN_PASSWORD="REDACTED" `
  TMONEY_WEBHOOK_SECRET="REDACTED" `
  -a nepxy-staging
```

## Validate OpenAPI + health (staging gate)
```powershell
$headers = @{ "X-Staging-Key" = $env:STAGING_GATE_KEY }
Invoke-RestMethod "$env:STAGING_BASE_URL/health" -Headers $headers
Invoke-RestMethod "$env:STAGING_BASE_URL/openapi.json" -Headers $headers
```

## Troubleshooting

### STAGING_GATE_KEY_REQUIRED
```powershell
$headers = @{ "X-Staging-Key" = $env:STAGING_GATE_KEY }
Invoke-RestMethod "$env:STAGING_BASE_URL/health" -Headers $headers
```

### INVALID_CREDENTIALS
```powershell
$env:CANARY_ALLOW_BOOTSTRAP="1"
python scripts\canary_smoke.py
```

### INVALID_SIGNATURE
```powershell
$env:CANARY_DEBUG_WEBHOOK_SIG="1"
python scripts\canary_smoke.py
```
