# Release Runbook (Staging)

## Release staging
```powershell
.\scripts\release_staging.ps1
```

What it does:
- Deploys to Fly (staging)
- Loads staging env from Fly
- Runs `scripts/canary_smoke.py`
- Prints rollback command on failure

## Rollback
```powershell
fly releases -a nepxy-staging
fly releases revert <RELEASE_ID> -a nepxy-staging
```

## Staging DB backup
```powershell
.\scripts\db_backup_staging.ps1
```
Backups are saved under `.\backups\`.

## Staging DB restore (destructive)
```powershell
$env:CONFIRM_RESTORE="YES"
.\scripts\db_restore_staging.ps1 -BackupFile .\backups\staging-db-YYYYMMDD-HHMMSS.sql
```

Notes:
- The restore script refuses to run without `CONFIRM_RESTORE=YES`.
- Both scripts use Fly SSH and rely on `DATABASE_URL` being present on the app.
