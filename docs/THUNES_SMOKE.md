# Thunes Smoke Scripts

## Local smoke
```
python scripts/smoke_thunes.py
```

Required env:
- `USER_EMAIL`, `USER_PASSWORD`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`

Optional:
- `THUNES_WEBHOOK_SECRET` (enables webhook post)
- `THUNES_DESTINATION_COUNTRY` (default `GH`)
- `WEBHOOK_DEBUG=1` (prints signature debug)

## Staging canary
```
python scripts/canary_thunes.py
```

Required env:
- `STAGING_BASE_URL`
- `STAGING_GATE_KEY` (if staging gate enabled)
- `STAGING_USER_EMAIL`, `STAGING_USER_PASSWORD`
- `STAGING_ADMIN_EMAIL`, `STAGING_ADMIN_PASSWORD`

Optional:
- `THUNES_WEBHOOK_SECRET` (enables webhook post)
- `THUNES_DESTINATION_COUNTRY` (default `GH`)
- `WEBHOOK_DEBUG=1`
