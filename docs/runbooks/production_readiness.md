# Nepxy API Production Readiness

## 1) Environments (dev/staging/prod)
- Debug routes: enabled in dev/staging; disabled in prod (e.g., `/debug/*` should 404).
- Gate key: staging may require `STAGING_GATE_KEY` header; prod should not rely on it.
- Providers: staging uses sandbox providers and secrets; prod uses live provider configs only.

Quick checks:
```bash
curl -sSf https://api.example.com/debug/version
```
```powershell
Invoke-RestMethod https://api.example.com/health
```

## 2) Secrets Inventory + Rotation
Critical env vars (no values here):
- `DATABASE_URL`
- `JWT_SECRET`
- `STAGING_GATE_KEY`
- `BOOTSTRAP_ADMIN_SECRET`
- `TMONEY_WEBHOOK_SECRET`
- `THUNES_WEBHOOK_SECRET`
- `MOMO_*` (all MoMo provider keys and callbacks)

Rotation guidance (no downtime):
1) Add new secret alongside old, if supported (dual-verify or dual-sign).
2) Deploy config update.
3) Switch traffic or validation to new secret.
4) Remove old secret after confirmation window.

Fly CLI examples:
```bash
flyctl secrets set JWT_SECRET="REDACTED" --app nepxy-api-prod
flyctl secrets unset JWT_SECRET_OLD --app nepxy-api-prod
```
PowerShell:
```powershell
flyctl secrets set JWT_SECRET="REDACTED" --app nepxy-api-prod
```

## 3) Observability
Request ID propagation:
- Expect `X-Request-ID` on responses.
- Log field `request_id` (or similar) must be present for traceability.

Search logs by request id:
```bash
flyctl logs --app nepxy-api-prod | rg "request_id=REQ_ID"
```
```powershell
flyctl logs --app nepxy-api-prod | Select-String -Pattern "request_id=REQ_ID"
```

## 4) Security Controls
- CORS: allow only known origins; no wildcard for prod.
- Rate limiting: enforce per-IP and per-token limits; monitor 429s.
- Auth hardening: strict JWT validation, short TTL, refresh and revocation plan.
- Admin-only routes: guard with role checks and audit logs.
- Debug routes: disabled in prod and excluded from OpenAPI.

## 5) Data Safety
- Backups: automated daily DB backups with retention.
- Restore drill: quarterly restore into staging, verify key endpoints.
- Migrations: use forward-only migrations; keep a rollback plan for each release.

Restore drill example:
```bash
flyctl postgres connect -a nepxy-db-prod
```

## 6) Payments/Webhooks Safety
- Idempotency: require `Idempotency-Key` for payout/cash-out flows.
- Retry/backoff: exponential backoff for provider calls and webhook retries.
- Webhook replay: keep raw payloads + signature headers for replay tooling.
- Signature verification: validate timestamp/nonce and HMAC signature before processing.

Webhook replay example:
```bash
curl -sS -X POST https://api.example.com/v1/webhooks/tmoney \
  -H "Content-Type: application/json" \
  -H "X-Signature: REDACTED" \
  -d '{"external_ref":"REDACTED","status":"SUCCESS"}'
```

## 7) Incident Runbooks

Disable provider:
```bash
flyctl secrets set PROVIDER_DISABLED="1" --app nepxy-api-prod
```

Maintenance mode:
```bash
flyctl secrets set MAINTENANCE_MODE="1" --app nepxy-api-prod
```
```powershell
Invoke-RestMethod https://api.example.com/health
```

Revoke tokens:
- Rotate `JWT_SECRET` and force re-auth.
```bash
flyctl secrets set JWT_SECRET="REDACTED" --app nepxy-api-prod
```

Rotate secrets quickly:
1) Set new secret in Fly.
2) Deploy.
3) Confirm logs + health checks.
4) Remove old secret when safe.

## Fly "Not Listening" Warnings
- Ensure the app binds to `0.0.0.0` and uses `PORT` (or `8001` fallback).
- Confirm `fly.toml` `internal_port` matches the server port and health checks hit `/health`.
- Check app logs for startup errors: `flyctl logs --app nepxy-api-prod`.
