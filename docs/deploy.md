# Deploy Guide (Staging -> Prod)

## Branching + Checks
- All changes land via PR into `main`.
- Required checks on PRs: `Pytest / test` (includes a syntax check).
- `main` merges trigger staging deploy and a staging canary.

## Staging Deploy (automatic or manual)
- Automatic on push to `main` via `Deploy Staging`.
- Manual: run `Deploy Staging` workflow (workflow_dispatch).
- After deploy, the workflow waits for `/health`, then runs the canary.

## Production Deploy (manual, gated)
- Run `Deploy Prod` workflow (manual only).
- Inputs:
  - `ref`: git ref to deploy (default `main`)
  - `app_name`: Fly app name (default `nepxy-prod`)
  - `base_url`: base URL for health check (default `https://nepxy-prod.fly.dev`)
  - `confirm`: must be `DEPLOY`
- Guardrail: refuses to deploy if the latest `Canary Staging / canary` run on `main` did not succeed.

## Rollback (Fly)
1) Find the prior release image.
2) Deploy the previous image:
   - `fly deploy --image <image> -a <app_name>`
3) Restart and verify health:
   - `fly machine restart -a <app_name>`
   - `curl -fsS https://<app>.fly.dev/health`
4) Re-run the staging canary (if staging is impacted).

## Required GitHub Secrets
Staging deploy + canary:
- `FLY_API_TOKEN`
- `STAGING_BASE_URL`
- `STAGING_GATE_KEY`
- `STAGING_USER_EMAIL`
- `STAGING_USER_PASSWORD`
- `STAGING_ADMIN_EMAIL`
- `STAGING_ADMIN_PASSWORD`
- `TMONEY_WEBHOOK_SECRET`
- `BOOTSTRAP_ADMIN_SECRET`

Prod deploy:
- `FLY_API_TOKEN`

## Notes
- Staging `/health` requires `X-Staging-Key`.
- Canary uses `scripts/canary_smoke.py` with env-based config only.
- No secrets should be committed to the repo; use Fly + GitHub Secrets.
