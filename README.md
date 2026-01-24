

\# NexaPay API (MVP)



FastAPI backend for wallets + ledger-backed transfers.



\## Features

\- Auth (JWT)

\- Wallet listing / balance

\- Wallet activity / transactions

\- P2P transfers with idempotency

\- DB error -> HTTP mapping (403/404/409 etc.)

\- Pytest suite (14 passing)



\## Run

```powershell

python -m uvicorn main:app --port 8001 --reload --reload-exclude .venv
```

\## Migrations

```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/nepxy"
alembic upgrade head
```

```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/nepxy"
alembic stamp head
```

```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/nepxy"
alembic revision -m "describe change"
alembic upgrade head
```

```powershell
# Production: run the same upgrade command against the prod DATABASE_URL
$env:DATABASE_URL="postgresql://user:pass@prod-host:5432/nepxy"
alembic upgrade head
```

\## Developer smoke test

```powershell
$env:BASE_URL="http://127.0.0.1:8001"
$env:USER_EMAIL="user@example.com"
$env:USER_PASSWORD="password123"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="password123"
$env:TMONEY_WEBHOOK_SECRET="dev_secret_tmoney"
python scripts/smoke_dev.py
```

\## Docker: required env vars for smoke test

- `docker compose` injects the local `.env` into the `app` (and `reconcile`) services via `env_file`, so populate that file with the keys below instead of passing them every run on the CLI.
- Ensure `.env` defines `USER_EMAIL`, `USER_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `TMONEY_WEBHOOK_SECRET` so the smoke test command works out of the box.
- `.env.example` already lists placeholders for those values; copy it to `.env` and customize before running the smoke test.

\## Secrets

\- Never commit secrets or production credentials to Git. `.env` is already ignored.
\- In production, set secrets via environment variables and enable `ENV=prod` to enforce required settings.
\- Store secrets in your deployment platform's secret manager and inject them at runtime.

\## Deploy

```powershell
# Local (venv)
python -m uvicorn main:app --port 8001 --reload --reload-exclude .venv
```

```powershell
# Containers (build + run)
docker compose up -d --build
```

```powershell
# Containers (run reconcile daemon profile)
docker compose --profile reconcile up -d --build
```

```powershell
# Apply migrations
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/nepxy"
alembic upgrade head
```

```powershell
# Smoke test
$env:BASE_URL="http://127.0.0.1:8001"
python scripts/smoke_dev.py
```

\## Staging rollout

```powershell
# Apply migrations
$env:DATABASE_URL="postgresql://user:pass@staging-host:5432/nepxy"
alembic upgrade head

# Seed staging users
python scripts/seed_staging.py

# Canary smoke
$env:STAGING_BASE_URL="https://staging.example.com"
python scripts/canary_smoke.py

# If green, promote
```

\## Backups

See `docs/BACKUPS.md` for backup/restore procedures.

\## Production notes

- Env var reference: `docs/env.production.md`
- Staging guide: `docs/staging.md`
- Rollback runbook: `docs/runbooks/rollback.md`
- Incident triage: `docs/runbooks/incident-triage.md`

\## Observability

- See `docs/observability.md` for request tracing and log queries.
