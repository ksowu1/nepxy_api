# Secrets and Rotation

This document lists secrets in use and recommended rotation guidance.
Never commit secrets. Store production/staging secrets in Fly secrets.

## Where secrets live
- Production: Fly secrets (`flyctl secrets set ...`)
- Staging: Fly secrets (use rotation scripts)
- Local dev: `.env` or shell env vars only

## Secrets (current)

| Secret | Purpose | Where used | Rotate? |
| --- | --- | --- | --- |
| STAGING_GATE_KEY | Staging access gate (`X-Staging-Key`). | `middleware.py:StagingGateMiddleware` | Yes (staging) |
| BOOTSTRAP_ADMIN_SECRET | Debug bootstrap auth in staging/dev. | `routes/debug.py` | Yes (staging/dev) |
| TMONEY_WEBHOOK_SECRET | Verify TMONEY webhooks. | `routes/webhooks.py` | Yes |
| THUNES_WEBHOOK_SECRET | Verify Thunes webhooks. | `routes/webhooks.py` | Yes |
| JWT_SECRET | JWT signing key. | `security.py` | Yes |
| DATABASE_URL / DB password | Database connection + auth. | `db.py`, `alembic/env.py` | Yes |
| Provider credentials | API auth for TMONEY/FLOOZ/MOMO/THUNES. | `settings.py` | Yes |

## Recommended minimums
- JWT secrets: 32+ chars.
- Webhook secrets: 40+ chars.
- Gate keys: 48+ chars.
- Passwords: 16+ chars.

## Rotation guidance
1) Generate a new secret.
2) Set in Fly secrets.
3) Restart machines.
4) Verify `/health` with `X-Staging-Key`.
5) Run canary (`scripts/canary_smoke.py`).

## Safe generators
PowerShell (Python):
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Shorter password:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(18))"
```

## Staging rotation helper
Use:
```powershell
.\scripts\rotate_secrets_staging.ps1
```
