# Backups

## Frequency
- Production: daily full backup.
- Staging: weekly full backup.
- Before risky changes: take an on-demand backup.

## Storage
- Store backups in encrypted storage (S3 with SSE, GCS KMS, or equivalent).
- Apply retention (e.g., 30 days).
- Restrict access to ops only.

## Backup (local or ops)

PowerShell:
```
scripts/backup_db.ps1
```

Bash:
```
./scripts/backup_db.sh
```

## Restore (test monthly)

PowerShell:
```
scripts/restore_db.ps1 -BackupFile backups/nepxy_backup_YYYYMMDD_HHMMSS.dump
```

Bash:
```
./scripts/restore_db.sh backups/nepxy_backup_YYYYMMDD_HHMMSS.dump
```

## Test restore checklist (monthly)
1) Restore into a non-prod database.
2) Run `alembic upgrade head` to ensure migrations are current.
3) Run smoke test against the restored DB.
4) Validate health endpoints and critical flows.

## RPO / RTO
- RPO (Recovery Point Objective): maximum acceptable data loss. Example: 24 hours if daily backups.
- RTO (Recovery Time Objective): maximum acceptable downtime. Example: 2 hours to restore and validate.
