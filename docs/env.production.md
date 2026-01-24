# Nepxy Production Environment Variables

This document lists required and optional environment variables for Nepxy.
Each entry includes what it controls and where it is used in code.

## Core

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| ENV | yes | `prod` | Runtime environment (dev/staging/prod/test). | `settings.py:ENV`, `main.py:_runtime_env` |
| ENVIRONMENT | no | `prod` | Alternate env var name for ENV. | `main.py:_runtime_env`, `middleware.py:StagingGateMiddleware` |
| APP_NAME | no | `nepxy-api` | Deployment label for ops and tooling. | not referenced in app code |
| BASE_URL | no | `https://api.nepxy.example` | Base URL used by scripts/tools. | `scripts/run_smoke.ps1`, `scripts/smoke_dev.py` |
| JWT_SECRET | yes | `change-me-32chars-min` | JWT signing key. | `security.py:create_access_token`, `settings.py:JWT_SECRET` |
| ACCESS_TOKEN_TTL_SECONDS | no | `3600` | Access token TTL (not wired; see JWT_ACCESS_MINUTES). | not referenced in app code |
| REFRESH_TOKEN_TTL_SECONDS | no | `2592000` | Refresh token TTL (not wired; see JWT_REFRESH_DAYS). | not referenced in app code |
| JWT_ACCESS_MINUTES | yes | `60` | Access token TTL in minutes. | `security.py:create_access_token`, `settings.py:JWT_ACCESS_MINUTES` |
| JWT_REFRESH_DAYS | yes | `30` | Refresh token TTL in days. | `security.py:create_session_refresh_token`, `settings.py:JWT_REFRESH_DAYS` |

## Database

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| DATABASE_URL | yes | `postgresql://user:pass@host:5432/nepxy` | Postgres connection string. | `db.py:init_pool`, `alembic/env.py` |
| DB_POOL_SIZE | no | `10` | Pool size (not wired; pool uses maxconn=10). | not referenced in app code |
| DB_POOL_TIMEOUT | no | `5` | Pool connect timeout (not wired; uses `connect_timeout=5`). | not referenced in app code |

## Staging Gate

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| STAGING_GATE_KEY | yes (staging only) | `staging-gate-secret` | Gate key to restrict staging traffic. | `middleware.py:StagingGateMiddleware` |
| X-Staging-Key (header) | yes (staging only) | `X-Staging-Key: <key>` | Request header used with STAGING_GATE_KEY. | `middleware.py:StagingGateMiddleware` |

## Bootstrap (dev/staging only)

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| BOOTSTRAP_ADMIN_SECRET | yes (staging/dev) | `bootstrap-admin-secret` | Enables debug bootstrap endpoints. | `routes/debug.py`, `scripts/canary_smoke.py` |

## Providers: Mobile Money

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| MM_ENABLED_PROVIDERS | yes | `TMONEY,FLOOZ,MTN_MOMO,THUNES` | Provider allowlist. | `app/providers/mobile_money/config.py:enabled_providers` |
| TMONEY_WEBHOOK_SECRET | yes (if TMONEY enabled) | `tmoney-secret` | TMONEY webhook signature secret. | `routes/webhooks.py:_get_secret`, `settings.py:TMONEY_WEBHOOK_SECRET` |
| THUNES_WEBHOOK_SECRET | yes (if THUNES enabled) | `thunes-secret` | Thunes webhook signature secret. | `routes/webhooks.py:_get_secret`, `settings.py:THUNES_WEBHOOK_SECRET` |
| THUNES_SANDBOX_API_ENDPOINT | yes (if THUNES sandbox) | `https://api.sandbox.thunes.com` | Thunes v2 API endpoint. | `settings.py:THUNES_SANDBOX_API_ENDPOINT` |
| THUNES_SANDBOX_API_KEY | yes (if THUNES sandbox) | `thunes-sandbox-key` | Thunes v2 API key. | `settings.py:THUNES_SANDBOX_API_KEY` |
| THUNES_SANDBOX_API_SECRET | yes (if THUNES sandbox) | `thunes-sandbox-secret` | Thunes v2 API secret. | `settings.py:THUNES_SANDBOX_API_SECRET` |

## Observability

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| LOG_LEVEL | no | `INFO` | Log verbosity (not wired; default logging config). | not referenced in app code |
| SENTRY_DSN | no | `https://public@o0.ingest.sentry.io/0` | Error reporting (not wired). | not referenced in app code |

## Fly/Runtime

| Name | Required? | Example | What it controls | Where used |
| --- | --- | --- | --- | --- |
| PORT | yes (runtime) | `8001` | HTTP listen port. | `main.py:_resolve_port`, `Dockerfile` |
| HOST | no | `0.0.0.0` | HTTP listen host (not env-wired; set in Dockerfile). | `Dockerfile` |

## Production Checklist
- Rotate secrets (JWT + provider secrets) before deploy.
- Set `ENV=prod` and ensure debug routes are disabled.
- Confirm healthcheck passes at `/health`.
- Run migrations against production database.
- Run staging canary before and after deploy.
