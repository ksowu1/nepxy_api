# Thunes Runbook

## Environment Sanity Check
Use the helper to verify required sandbox env vars are set (no values printed):
```bash
python scripts/check_thunes_env.py
```
Exit codes: `0` all present, `2` missing one or more.
