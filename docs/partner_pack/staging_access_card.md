# Staging Access Card (NepXy)

## Base URL
- https://nepxy-staging.fly.dev

## Required gate header
- Header: `X-Staging-Key: <staging_gate_key>`
- Example:
  `curl https://nepxy-staging.fly.dev/health -H "X-Staging-Key: <staging_gate_key>"`

## Test credentials (format only)
User:
- Email: <staging_user_email>
- Password: <staging_user_password>

Admin:
- Email: <staging_admin_email>
- Password: <staging_admin_password>

## Canary smoke
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\_env_staging_from_fly.ps1
python .\scripts\canary_smoke.py
```

## Support
- Email: <support_email>
- Hours: <support_hours>
