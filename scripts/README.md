# Scripts

## Request Tracing

Capture the request id from a staging request:

```powershell
$resp = Invoke-WebRequest -Method Get -Uri "$env:STAGING_BASE_URL/health" -Headers @{ "X-Staging-Key" = $env:STAGING_GATE_KEY }
$requestId = $resp.Headers["X-Request-ID"]
```

Trace it in Fly logs:

```powershell
fly logs -a nepxy-staging | Select-String -Pattern $requestId
```

Or use the helper script:

```powershell
.\scripts\find_request.ps1 -RequestId $requestId
```
