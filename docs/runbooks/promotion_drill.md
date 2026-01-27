# Promotion Drill (Rehearsal)

Safe production promotion rehearsal without enabling real providers.

## Usage
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\promotion_drill.ps1
```

Dry run (prints actions only):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\promotion_drill.ps1 -DryRun
```

## Steps performed
1) Assert required tools exist (fly, python)
2) Load staging env from Fly (`scripts/_env_staging_from_fly.ps1`)
3) Run staging canary (`scripts/canary_smoke.py`)
4) Take staging DB backup (`scripts/db_backup_staging.ps1`)
5) Ensure prod app exists; if missing, print exact create commands and exit
6) Validate `fly.prod.toml` (`fly config validate -c fly.prod.toml`)
7) Deploy to prod (`fly deploy -c fly.prod.toml --remote-only`)
8) Run prod smoke (`scripts/prod_smoke.ps1`)
9) Print rollback commands and backup folder path

## Expected output (abridged)
```
==> Load staging env from Fly (dot-source)
==> Run staging canary (must be green)
==> Staging DB backup
==> Ensure prod app exists
==> Validate fly.prod.toml
==> Deploy to prod (remote-only)
==> Run prod smoke
==> Rollback (manual)
```

## Troubleshooting
- Staging canary fails: fix staging before continuing.
- Backup fails: check Fly auth and `pg_dump` availability on staging machine.
- Prod app missing: run the printed create commands, then rerun.
- Config validate fails: fix `fly.prod.toml` before deploying.

## Rollback
```
fly releases --app nepxy-prod
fly deploy --image <digest> --app nepxy-prod
```
