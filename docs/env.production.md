# Nepxy API Production Environment Variables

Use this as the source of truth for required/optional env vars in production.
Never commit secrets. Store them in Fly secrets (or your platform's secret store).

Notes:
- Staging gate header is `X-Staging-Key` (staging only).
- In staging, `/health` requires `X-Staging-Key`.
- Debug routes live under `/debug` and should be disabled in prod.

## Release Flow (PR -> Staging -> Prod)

- PRs must pass `Pytest / test` before merge.
- Push to `main` triggers staging deploy (Fly) and uploads deploy metadata.
- Staging canary runs on demand or after deploy.
- Production deploy is manual and promotes the exact staging image digest (no rebuild).
- Rollback: redeploy a previous digest using `fly deploy --image <digest> -a nepxy-prod`.

### GitHub Environments + Secrets

Create GitHub environments: `staging`, `production`.
- `production` should require manual approval.

Staging environment secrets:
- `FLY_API_TOKEN`
- `STAGING_BASE_URL` (https://nepxy-staging.fly.dev)
- `STAGING_GATE_KEY`
- `STAGING_USER_EMAIL`
- `STAGING_USER_PASSWORD`
- `STAGING_ADMIN_EMAIL`
- `STAGING_ADMIN_PASSWORD`
- `TMONEY_WEBHOOK_SECRET`
- `BOOTSTRAP_ADMIN_SECRET` (optional, if canary bootstrap is allowed)
- `CANARY_ALLOW_BOOTSTRAP` (optional, default is `1`)

Production environment secrets:
- `FLY_API_TOKEN`

Fly apps used in workflows:
- `nepxy-staging`
- `nepxy-prod`

## Core

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| ENV | yes | `prod` | `dev` | Runtime environment. | `settings.py:ENV`, `main.py:_runtime_env` |
| ENVIRONMENT | no | `prod` | (none) | Alternate env name for ENV. | `main.py:_runtime_env`, `middleware.py:StagingGateMiddleware` |
| APP_NAME | no | `nepxy-api` | (none) | Deployment label for ops/tools. | not referenced in app code |
| BASE_URL | no | `https://api.nepxy.example` | (none) | Base URL for scripts/tools. | `scripts/run_smoke.ps1`, `scripts/smoke_dev.py` |
| PORT | yes (runtime) | `8001` | `8001` | HTTP listen port. | `main.py:_resolve_port`, `Dockerfile` |
| HOST | no | `0.0.0.0` | `0.0.0.0` | HTTP bind host (set in Dockerfile). | `Dockerfile` |

## Database

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| DATABASE_URL | yes | `postgresql://user:pass@host:5432/nepxy` | (none) | Postgres DSN. | `db.py:init_pool`, `alembic/env.py` |
| DB_POOL_SIZE | no | `10` | (none) | Pool size (not wired; maxconn=10 is hardcoded). | not referenced in app code |
| DB_POOL_TIMEOUT | no | `5` | (none) | Pool connect timeout (not wired; connect_timeout=5 is hardcoded). | not referenced in app code |

## Auth / JWT

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| JWT_SECRET | yes | `change-me-32chars-min` | (none) | JWT signing key. | `security.py:create_access_token`, `settings.py:JWT_SECRET` |
| JWT_ALG | no | `HS256` | `HS256` | JWT signing algorithm. | `settings.py:JWT_ALG` |
| JWT_ACCESS_MINUTES | yes | `60` | `60` | Access token TTL (minutes). | `security.py:create_access_token`, `settings.py:JWT_ACCESS_MINUTES` |
| JWT_REFRESH_DAYS | yes | `30` | `30` | Refresh token TTL (days). | `security.py:create_session_refresh_token`, `settings.py:JWT_REFRESH_DAYS` |
| ACCESS_TOKEN_TTL_SECONDS | no | `3600` | (none) | Placeholder only (not wired). | not referenced in app code |
| REFRESH_TOKEN_TTL_SECONDS | no | `2592000` | (none) | Placeholder only (not wired). | not referenced in app code |

## Mobile Money (Global)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| MM_MODE | yes | `real` | `sandbox` | Provider mode. | `settings.py:MM_MODE`, `app/providers/mobile_money/config.py:mm_mode` |
| MM_ENABLED_PROVIDERS | yes | `TMONEY,FLOOZ,MTN_MOMO,THUNES` | (none) | Provider allowlist. | `app/providers/mobile_money/config.py:enabled_providers` |
| THUNES_ENABLED | no | `true` | `false` | Toggle Thunes validation + runtime usage. | `settings.py:THUNES_ENABLED` |
| MM_STRICT_STARTUP_VALIDATION | no | `true` | `false` | Enforce strict startup validation. | `app/providers/mobile_money/validate.py` |
| MM_HTTP_TIMEOUT_S | no | `20.0` | `20.0` | Provider HTTP timeout. | `settings.py:MM_HTTP_TIMEOUT_S` |
| MOMO_HTTP_TIMEOUT_S | no | `20.0` | `20.0` | MoMo HTTP timeout. | `settings.py:MOMO_HTTP_TIMEOUT_S` |

## Webhooks (Mobile Money)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| TMONEY_WEBHOOK_SECRET | yes (if TMONEY enabled) | `tmoney-secret` | (none) | TMONEY webhook signature. | `routes/webhooks.py:_get_secret` |
| FLOOZ_WEBHOOK_SECRET | yes (if FLOOZ enabled) | `flooz-secret` | (none) | FLOOZ webhook signature. | `routes/webhooks.py:_get_secret` |
| MOMO_WEBHOOK_SECRET | yes (if MTN_MOMO enabled) | `momo-secret` | (none) | MoMo webhook signature. | `routes/webhooks.py:_get_secret` |
| THUNES_WEBHOOK_SECRET | yes (if THUNES enabled) | `thunes-secret` | (none) | Thunes webhook signature. | `routes/webhooks.py:_get_secret` |
| THUNES_ALLOW_UNSIGNED_WEBHOOKS | no (ignored in prod) | `false` | `true` | Allow unsigned Thunes webhooks (sandbox only). | `routes/webhooks.py` |

## Thunes (Placeholders + Current)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| THUNES_SANDBOX_API_ENDPOINT | placeholder | `https://api.sandbox.thunes.com` | (none) | Thunes v2 API endpoint. | `settings.py:THUNES_SANDBOX_API_ENDPOINT` |
| THUNES_SANDBOX_API_KEY | placeholder | `thunes-sandbox-key` | (none) | Thunes v2 API key. | `settings.py:THUNES_SANDBOX_API_KEY` |
| THUNES_SANDBOX_API_SECRET | placeholder | `thunes-sandbox-secret` | (none) | Thunes v2 API secret. | `settings.py:THUNES_SANDBOX_API_SECRET` |
| THUNES_REAL_API_ENDPOINT | yes (prod, if THUNES enabled) | `https://api.thunes.com` | (none) | Thunes v2 API endpoint. | `settings.py:THUNES_REAL_API_ENDPOINT` |
| THUNES_REAL_API_KEY | yes (prod, if THUNES enabled) | `thunes-real-key` | (none) | Thunes v2 API key. | `settings.py:THUNES_REAL_API_KEY` |
| THUNES_REAL_API_SECRET | yes (prod, if THUNES enabled) | `thunes-real-secret` | (none) | Thunes v2 API secret. | `settings.py:THUNES_REAL_API_SECRET` |
| THUNES_PAYER_ID_GH | yes (if THUNES enabled) | `payer-gh` | (none) | Payer id for GH. | `settings.py:THUNES_PAYER_ID_GH` |

Enable Thunes later:
- Set `THUNES_ENABLED=true`.
- Keep `MM_ENABLED_PROVIDERS` including `THUNES`.
- Add the THUNES_* API endpoint/key/secret and `THUNES_PAYER_ID_GH`.

Discover Thunes payer_id for Ghana:
- Use the Thunes Discovery API to list payers for Ghana and copy the `id` of the payer you want.
- Example (placeholder; use your Thunes base URL and credentials):
  `GET {THUNES_*_API_ENDPOINT}/v2/money-transfer/payers` then filter for country `GH` in the response.

## Observability

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| LOG_LEVEL | no | `INFO` | (none) | Log verbosity (not wired). | not referenced in app code |
| SENTRY_DSN | no | `https://public@o0.ingest.sentry.io/0` | (none) | Error reporting (not wired). | not referenced in app code |

## Email/SMS (Placeholders)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| EMAIL_PROVIDER_API_KEY | placeholder | `email-api-key` | (none) | Email provider credentials. | not referenced in app code |
| SMS_PROVIDER_API_KEY | placeholder | `sms-api-key` | (none) | SMS provider credentials. | not referenced in app code |

## Staging Gate (staging only)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| STAGING_GATE_KEY | yes (staging) | `staging-gate-secret` | (none) | Staging access gate. | `middleware.py:StagingGateMiddleware` |
| X-Staging-Key (header) | yes (staging) | `X-Staging-Key: <key>` | (none) | Staging request header. | `middleware.py:StagingGateMiddleware` |

## Bootstrap (dev/staging only)

| Name | Required? | Example | Safe default | What it controls | Where used |
| --- | --- | --- | --- | --- | --- |
| BOOTSTRAP_ADMIN_SECRET | yes (staging/dev) | `bootstrap-admin-secret` | (none) | Enables `/debug/bootstrap-*`. | `routes/debug.py`, `scripts/canary_smoke.py` |
