# Fly Postgres Backup + Restore Runbook

This runbook covers safe backup/restore workflows for staging and prod.

## 1) Identify Postgres App + Attachments
List apps and Postgres clusters:
```bash
flyctl apps list
flyctl postgres list
```
Check attachments for an app:
```bash
flyctl postgres attachments --app nepxy-staging
flyctl postgres attachments --app nepxy-api-prod
```

## 2) Logical Backup (pg_dump)
Preferred: use a read-only connection string (DATABASE_URL).

Option A: Direct `DATABASE_URL`
```bash
pg_dump --format=custom --file=backup.dump "$DATABASE_URL"
```

Option B: Fly proxy (no public DB)
```bash
flyctl proxy 15432:5432 --app nepxy-staging-db
```
Then in another shell:
```bash
pg_dump --format=custom --file=backup.dump "postgresql://user:pass@localhost:15432/nepxy"
```

Option C: Fly SSH console on the app and use env vars
```bash
flyctl ssh console --app nepxy-staging
pg_dump --format=custom --file=/tmp/backup.dump "$DATABASE_URL"
```
Then copy the file out:
```bash
flyctl ssh sftp get /tmp/backup.dump ./backup.dump --app nepxy-staging
```

## 3) Restore (pg_restore)
Safety: restore into a new DB or new cluster when possible.

Restore into a new DB (recommended):
```bash
createdb --host localhost --port 15432 --username postgres nepxy_restored
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "postgresql://user:pass@localhost:15432/nepxy_restored" backup.dump
```

Restore into an existing DB (dangerous):
```bash
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$DATABASE_URL" backup.dump
```

## 4) Volume Snapshots (if applicable)
For persistent volumes (not a substitute for pg_dump):
```bash
flyctl volumes list --app nepxy-staging
flyctl volumes snapshots list -a nepxy-staging --volume <volume-id>
flyctl volumes snapshots create -a nepxy-staging --volume <volume-id>
```

## 5) Safety Notes
- Do NOT restore into prod without explicit approval.
- Prefer restoring into a new cluster and validating before cutover.
- Rotate DB credentials after restore.
- Validate migrations and key endpoints before resuming traffic.

