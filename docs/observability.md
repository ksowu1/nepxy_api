# Observability

## Trace a request with X-Request-ID
- Send `X-Request-ID` in the request to correlate logs.
- If missing, the API generates one and returns it in the response header.

Example:
```bash
curl -sS https://nepxy-staging.fly.dev/health -H "X-Request-ID: manual-req-1" -H "X-Staging-Key: $STAGING_GATE_KEY"
```

## Fly log examples
Request start/end logs are written as key=value:
```
http_request_start request_id=... method=GET path=/health
http_request_end request_id=... method=GET path=/health status=200 duration_ms=12
```

Error logs include error_code and reason:
```
http_request_error request_id=... method=POST path=/v1/auth/login http_status=401 error_code=INVALID_CREDENTIALS reason=INVALID_CREDENTIALS
```

## Common queries
Local logs:
```bash
rg "request_id=manual-req-1" staging_logs.txt
```

Fly logs:
```bash
flyctl logs --app nepxy-staging | rg "request_id=manual-req-1"
```

## Scripted lookup
Use the helper script to search Fly logs by request_id:
```powershell
.\scripts\find_request.ps1 -RequestId manual-req-1 -App nepxy-staging
```
