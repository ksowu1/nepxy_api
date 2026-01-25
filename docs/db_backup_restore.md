# Database Backup & Restore

This guide covers production-safe backups and restores using Postgres tooling.

Prereqs:
- `pg_dump`, `pg_restore`, and `psql` on PATH
- `DATABASE_URL` (or `FLY_DATABASE_URL`) exported for the target database

## Backup

Linux/macOS (bash):
```bash
scripts/db_backup.sh
```

Windows (PowerShell):
```powershell
scripts\db_backup.ps1
```

Backups are written to `./backups` with a timestamp + git sha suffix.

## Restore (safe)

Restore is destructive. It requires an explicit flag and blocks production
unless `ALLOW_PROD_RESTORE=1` is set. If `ENV=production`, set the allow flag
only for controlled restores.

Linux/macOS:
```bash
scripts/db_restore.sh --i-know-what-im-doing backups/nepxy_backup_<timestamp>_<sha>.dump
```

Windows:
```powershell
scripts\db_restore.ps1 -BackupFile backups\nepxy_backup_<timestamp>_<sha>.dump -Iknowwhatimdoing
```

## Validate

Runs invariant row counts and validates `alembic_version` matches the current
Alembic head.

Linux/macOS:
```bash
scripts/db_validate.sh
```

Windows:
```powershell
scripts\db_validate.ps1
```

## Staging vs Production

- Staging: export the staging database URL and run the commands above.
- Production: requires `ENV=production` and `ALLOW_PROD_RESTORE=1` to restore.

Example (bash):
```bash
export ENV=production
export ALLOW_PROD_RESTORE=1
export DATABASE_URL="postgresql://..."
scripts/db_restore.sh --i-know-what-im-doing backups/nepxy_backup_<timestamp>_<sha>.dump
```
