# Release Runbook (Production Promotion + Rollback)

This runbook assumes staging is stable and production is next. Staging app: `nepxy-staging`. Production app: `nepxy-prod`.

## Preconditions checklist
- [ ] Tests green (local + CI): `pytest` and `.github/workflows/pytest.yml`.
- [ ] Canary staging green (nightly + on-demand): `.github/workflows/staging-canary.yml`.
- [ ] Migrations ready and reviewed (see `docs/MIGRATION_POLICY.md`).
- [ ] Backup taken and stored (see `scripts/db_backup.ps1` or `scripts/db_backup.sh`).
- [ ] Secrets set in production (`fly secrets list --app nepxy-prod`).
- [ ] Debug routes disabled in prod (e.g., `/debug/version` and `/debug/*` return 404).

## Promotion flow
1) Tag release (from `main`) and push tags.
2) Deploy to production.
3) Run health checks (`/health`, `/readyz`).
4) Run canary against prod (no bootstrap).
5) Verify logs and error rates.
6) Verify payment flows in sandbox mode (no live money).

## Rollback plan
1) Roll back Fly release.
2) DB rollback strategy:
   - If migration is backward compatible: roll back code only.
   - If not backward compatible: restore from backup and redeploy previous image.
3) Capture incident notes (template below).

## Commands

### Tag release
```powershell
git tag v<YYYYMMDD>-<n>
git push
git push --tags
```

### Deploy to production (Fly)
```powershell
fly deploy --app nepxy-prod --image <image_ref> --remote-only
```

### Health checks
```powershell
Invoke-WebRequest -UseBasicParsing https://nepxy-prod.fly.dev/health
Invoke-WebRequest -UseBasicParsing https://nepxy-prod.fly.dev/readyz
```

### Canary against prod (no bootstrap)
```powershell
$env:STAGING_BASE_URL="https://nepxy-prod.fly.dev"
$env:STAGING_USER_EMAIL="prod-sandbox-user@example.com"
$env:STAGING_USER_PASSWORD="..."
$env:STAGING_ADMIN_EMAIL="prod-sandbox-admin@example.com"
$env:STAGING_ADMIN_PASSWORD="..."
$env:CANARY_ALLOW_BOOTSTRAP="0"
python scripts\canary_smoke.py
```

### Verify logs/errors
```powershell
fly logs --app nepxy-prod
```

### Verify payments in sandbox (no live money)
```powershell
$env:MOMO_ENV="sandbox"
$env:MOMO_API_USER_ID="..."
$env:MOMO_API_KEY="..."
$env:MOMO_DISBURSE_SUB_KEY="..."
python scripts\momo_smoke.py
```

### Backup + validate (pre-deploy)
```powershell
scripts\db_backup.ps1
scripts\db_validate.ps1
```

### Rollback Fly release
```powershell
fly releases --app nepxy-prod
fly releases revert <RELEASE_ID> --app nepxy-prod
```

### Restore DB (destructive)
```powershell
$env:ENV="production"
$env:ALLOW_PROD_RESTORE="1"
scripts\db_restore.ps1 -BackupFile backups\nepxy_backup_<timestamp>_<sha>.dump -Iknowwhatimdoing
```

## Incident notes template
```
Date/Time (UTC):
Release tag:
Fly release ID:
Summary:
Impact:
Root cause:
Timeline:
- T0:
- T+:
Mitigations:
Rollback steps taken:
Follow-ups / action items:
```
