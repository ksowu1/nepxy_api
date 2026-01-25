# NepXy Production Runbook

Practical steps for deploy, verification, incident response, and rollback.
See `docs/fly_prod_setup.md` for Fly app config separation and production secrets.

## Deploy

1) Prepare environment variables
- Set required secrets and database URL.
- Set `ENV=prod`.
- Configure `CORS_ALLOW_ORIGINS` with your UI domains.

Example (shell):
```
DATABASE_URL=postgresql://user:pass@db-host:5432/nepxy
ENV=prod
JWT_SECRET=... (min 16 chars)
TMONEY_WEBHOOK_SECRET=...
FLOOZ_WEBHOOK_SECRET=...
MOMO_WEBHOOK_SECRET=...
THUNES_WEBHOOK_SECRET=...
CORS_ALLOW_ORIGINS=https://app.example.com,https://admin.example.com
```

2) Build and run (Docker)
```
docker compose up -d --build
```

3) Run migrations
```
alembic upgrade head
```

4) Start worker (if not already part of your deployment)
```
python -m app.workers.payout_worker
```

## Verify health

1) Health check
```
GET /healthz
```
Expected: `ok=true` and `db_ok=true`.

2) Readiness check
```
GET /readyz
```
Expected: `ready=true` and `migrations_ok=true`.

3) Metrics
```
GET /metrics
```
Expect Prometheus counters:
- `http_requests_total`
- `payout_attempts_total`
- `webhook_events_total`
- `idempotency_replays_total`

## Rotate secrets

1) Add new secrets in your secret manager.
2) Deploy with new env vars (do not remove old secrets if you need overlap).
3) Verify `healthz`, `readyz`, and critical flows.
4) Remove old secrets after validation.

JWT rotation:
- Changing `JWT_SECRET` invalidates existing access tokens.
- Plan a maintenance window if needed.

Webhook secret rotation:
- Coordinate with providers to accept new signature key.
- Temporarily accept both if provider supports it.

## Incident response

### 1) Payouts stuck in SENT
Symptoms:
- Payouts remain `SENT` and do not transition.

Steps:
1) Check worker is running and healthy.
2) Inspect `app.mobile_money_payouts` for `attempt_count` and `next_retry_at`.
3) Verify provider status polling works.
4) Use admin retry:
```
POST /v1/admin/mobile-money/payouts/{transaction_id}/retry
```
5) If provider ref missing, resend is triggered automatically by worker.

### 2) Webhook signature failures spike
Symptoms:
- `webhook_events_total{signature_valid="false"}` increases rapidly.

Steps:
1) Verify webhook secrets in env.
2) Check request body and signature scheme from provider.
3) If a deployment changed parsing, roll back or hotfix.
4) If provider rotated secret, update it immediately.

### 3) Provider downtime
Symptoms:
- `payout_attempts_total{result="FAILED"}` spikes.

Steps:
1) Confirm provider status page.
2) Increase backoff or pause retries if needed.
3) Use manual retries when provider recovers.
4) Communicate delays to support.

### 4) Duplicate request / idempotency issues
Symptoms:
- Clients report duplicate actions or `IDEMPOTENCY_CONFLICT`.

Steps:
1) Ensure clients reuse the same Idempotency-Key for retries.
2) Check `app.idempotency_keys` for conflicts.
3) For a specific request, re-run using the stored response.
4) If conflicts are unexpected, inspect request payload differences.

### 5) DB connection pool exhaustion
Symptoms:
- 500s or timeouts, slow requests.

Steps:
1) Check DB connections and max limits.
2) Reduce app concurrency or increase pool size.
3) Look for slow queries or long-running transactions.
4) Restart app if pool is wedged.

## Safe rollback

1) Re-deploy previous container image or git SHA.
2) Verify `readyz` is healthy.
3) Run smoke test to confirm core flows.
4) If a migration was applied, do not downgrade unless verified safe.

## Post-deploy checklist

1) `make release-check`
2) `python scripts/smoke_dev.py` (against prod/staging base URL)
3) Verify `/healthz`, `/readyz`, `/metrics`
4) Confirm admin payout and webhook flows
