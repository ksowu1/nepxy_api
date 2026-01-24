# Incident Triage

## First five checks
1) Health endpoint:
```bash
curl -sS https://nepxy-staging.fly.dev/health -H "X-Staging-Key: $STAGING_GATE_KEY"
```
2) OpenAPI routes:
```bash
curl -sS https://nepxy-staging.fly.dev/openapi.json -H "X-Staging-Key: $STAGING_GATE_KEY" | rg "\"/v1/"
```
3) Login:
```powershell
$body = @{ email=$env:STAGING_USER_EMAIL; password=$env:STAGING_USER_PASSWORD } | ConvertTo-Json
Invoke-RestMethod "$env:STAGING_BASE_URL/v1/auth/login" -Method Post -Headers @{ "X-Staging-Key" = $env:STAGING_GATE_KEY } -Body $body -ContentType "application/json"
```
4) Canary:
```powershell
$env:CANARY_ALLOW_BOOTSTRAP="1"
python scripts\canary_smoke.py
```
5) Webhook signature:
```bash
curl -sS -X POST https://nepxy-staging.fly.dev/v1/webhooks/tmoney -H "X-Signature: REDACTED" -H "Content-Type: application/json" -d '{"external_ref":"REDACTED","status":"SUCCESS"}'
```

## Request ID correlation
- Capture `X-Request-ID` from API responses.
- Search logs for the same `request_id`:
```bash
flyctl logs --app nepxy-staging | rg "request_id=<ID>"
```
