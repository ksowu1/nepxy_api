# Staging Canary Smoke

## Steps
1) Dot-source staging env:
   ```powershell
   . .\scripts\_env_staging_from_fly.ps1
   ```
2) Optional: allow bootstrap on invalid credentials:
   ```powershell
   $env:CANARY_ALLOW_BOOTSTRAP="1"
   ```
3) Run canary:
   ```powershell
   python scripts\canary_smoke.py
   ```

## Staging Recovery Script
If staging is in a bad state (credentials rotated, canary failing), run:
```powershell
.\scripts\staging_recover.ps1
```
This loads staging env, restarts the Fly machine, and runs the canary with bootstrap enabled.

## Common failure modes
- `STAGING_GATE_KEY_REQUIRED`: ensure `STAGING_GATE_KEY` is loaded and the request includes `X-Staging-Key`.
- `INVALID_CREDENTIALS`: rotate Fly secrets and re-bootstrap staging users before retrying.
- `INVALID_SIGNATURE`: confirm `TMONEY_WEBHOOK_SECRET` matches staging; use `CANARY_DEBUG_WEBHOOK_SIG=1` to print only lengths/prefixes.

## Safe debugging
- Do not print secrets or tokens.
- Only print secret lengths or short prefixes (e.g., first 10 chars) when needed.
