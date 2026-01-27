# Fly Production Setup (NepXy)

This doc describes how to keep staging and production isolated on Fly and how to deploy safely.

## Config separation
- Staging config: `fly.staging.toml` (app: `nepxy-staging`)
- Production config: `fly.prod.toml` (app: `nepxy-prod`)
- Keep `fly.toml` aligned with staging defaults; use `-c` when deploying.

## Safe deploy commands

### Staging deploy
```powershell
fly deploy -c fly.staging.toml --app nepxy-staging --remote-only
```

### Production deploy
```powershell
fly deploy -c fly.prod.toml --app nepxy-prod --remote-only
```

## Production guardrails
- Debug router is not mounted when `ENV`/`ENVIRONMENT` is `prod` or `production`.
- Bootstrap endpoints return 404 in production even if hit.
- Staging gate header (`X-Staging-Key`) is enforced only when `ENV=staging`.

## Production secrets checklist

Set secrets with:
```powershell
fly secrets set --app nepxy-prod ^
  ENV="prod" ^
  DATABASE_URL="postgresql://..." ^
  JWT_SECRET="..." ^
  MM_MODE="real" ^
  MM_ENABLED_PROVIDERS="TMONEY,FLOOZ,MTN_MOMO,THUNES" ^
  THUNES_ENABLED="false"
```

Core:
- `ENV=prod`
- `DATABASE_URL`
- `JWT_SECRET` (min 16 chars)
- `CORS_ORIGINS` (comma-separated allowed UI origins)

TMONEY (if enabled):
- `TMONEY_WEBHOOK_SECRET`
- `TMONEY_REAL_API_KEY`
- `TMONEY_REAL_CASHOUT_URL`
- `TMONEY_REAL_STATUS_URL_TEMPLATE`

FLOOZ (if enabled):
- `FLOOZ_WEBHOOK_SECRET`
- `FLOOZ_REAL_API_KEY`
- `FLOOZ_REAL_CASHOUT_URL`
- `FLOOZ_REAL_STATUS_URL_TEMPLATE`

MTN MOMO (if enabled):
- `MOMO_WEBHOOK_SECRET`
- `MOMO_REAL_API_USER`
- `MOMO_REAL_API_KEY`
- `MOMO_REAL_SUBSCRIPTION_KEY_DISBURSEMENT`
- `MOMO_REAL_BASE_URL`

THUNES (if enabled):
- `THUNES_ENABLED=true`
- `THUNES_WEBHOOK_SECRET`
- `THUNES_REAL_API_ENDPOINT`
- `THUNES_REAL_API_KEY`
- `THUNES_REAL_API_SECRET`
- `THUNES_REAL_CLIENT_ID`
- `THUNES_REAL_CLIENT_SECRET`
- `THUNES_REAL_TOKEN_URL`
- `THUNES_PAYER_ID_GH`
- `THUNES_PAYER_ID_TG`
- `THUNES_PAYER_ID_BJ`

Note: In production, unsigned Thunes webhooks are never accepted (THUNES_ALLOW_UNSIGNED_WEBHOOKS is ignored).

Enable Thunes later:
- Set `THUNES_ENABLED=true`.
- Add the THUNES_* secrets above.
- Restart the app (or redeploy) to pick up secrets.

Discover Thunes payer_id for Ghana:
- Call Thunes Discovery to list payers and select the Ghana payer `id`.
- Example (placeholder; use your Thunes base URL and credentials):
  `GET {THUNES_*_API_ENDPOINT}/v2/money-transfer/payers` then filter for country `GH`.

Bootstrap/debug (unused in prod):
- `BOOTSTRAP_ADMIN_SECRET` (should be unset in production)
- `STAGING_GATE_KEY` (staging only)
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `USER_EMAIL`, `USER_PASSWORD` (staging bootstrap only)

## Verify production
```powershell
Invoke-WebRequest -UseBasicParsing https://nepxy-prod.fly.dev/health
Invoke-WebRequest -UseBasicParsing https://nepxy-prod.fly.dev/readyz
```
