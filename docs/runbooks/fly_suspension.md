# Fly Suspension Runbook

## Detect a suspended app
- Status check:
  ```bash
  fly status --app nepxy-prod
  ```
- Logs may show no new activity or failed starts.
- Dashboard may display “suspended” or billing warnings.

## Resume the app
- Resume machines:
  ```bash
  fly machine list --app nepxy-prod
  fly machine start <machine_id> --app nepxy-prod
  ```
- If multiple machines:
  ```bash
  fly machine start <id1> --app nepxy-prod
  fly machine start <id2> --app nepxy-prod
  ```

## Common causes
- Billing issue (card expired, payment failure)
- Resource limits exceeded (memory/CPU)
- Manual suspension
- Idle/sleep policies on hobby plans

## Prevention checklist (prod)
- Ensure billing is active and payment method is valid
- Keep `min_machines_running` set appropriately
- Monitor memory/CPU and scale before hitting limits
- Run periodic health checks (`/health`, `/readyz`)
- Keep a recent DB backup

## Notes
- After resume, verify health:
  ```bash
  fly status --app nepxy-prod
  curl -sS https://nepxy-prod.fly.dev/health
  ```
