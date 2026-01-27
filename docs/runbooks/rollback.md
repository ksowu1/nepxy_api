# Rollback Runbook

## Fly rollback steps
1) Identify previous image or release:
```bash
flyctl releases --app nepxy-staging
```
2) Deploy a previous image:
```bash
flyctl deploy --app nepxy-staging --image registry.fly.io/nepxy-staging:<tag>
```
3) Restart machines:
```bash
flyctl machine restart --app nepxy-staging
```
4) Verify health:
```bash
curl -sS https://nepxy-staging.fly.dev/health -H "X-Staging-Key: $STAGING_GATE_KEY"
```
5) Re-run canary:
```bash
python scripts/canary_smoke.py
```

## Find request_id in logs
Local log file:
```powershell
rg "request_id=<ID>" .\staging_logs.txt
```
Fly logs:
```bash
flyctl logs --app nepxy-staging | rg "request_id=<ID>"
```
Note: `flyctl logs` may not support `--since` in all versions.
