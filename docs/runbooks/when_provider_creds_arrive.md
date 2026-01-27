# When Provider Credentials Arrive

This runbook covers enabling a provider after credentials are received.

## 1) Enable the provider flag
- Staging first, then production.
- Example (TMONEY):
  ```powershell
  fly secrets set --app nepxy-staging TMONEY_ENABLED="true"
  ```

## 2) Set secrets (staging)
### TMONEY (staging)
```powershell
fly secrets set --app nepxy-staging ^
  TMONEY_WEBHOOK_SECRET="<secret>" ^
  TMONEY_SANDBOX_API_KEY="<key>" ^
  TMONEY_SANDBOX_CASHOUT_URL="<cashout_url>"
```

### MTN MoMo (staging)
```powershell
fly secrets set --app nepxy-staging ^
  MOMO_WEBHOOK_SECRET="<secret>" ^
  MOMO_SANDBOX_BASE_URL="<base_url>" ^
  MOMO_SANDBOX_SUBSCRIPTION_KEY_DISBURSEMENT="<sub_key>" ^
  MOMO_SANDBOX_API_USER="<api_user>" ^
  MOMO_SANDBOX_API_KEY="<api_key>"
```

### Thunes (staging)
```powershell
fly secrets set --app nepxy-staging ^
  THUNES_ENABLED="true" ^
  THUNES_WEBHOOK_SECRET="<secret>" ^
  THUNES_SANDBOX_API_ENDPOINT="<endpoint>" ^
  THUNES_SANDBOX_API_KEY="<key>" ^
  THUNES_SANDBOX_API_SECRET="<secret>" ^
  THUNES_PAYER_ID_GH="<payer_id>"
```

## 3) Run sandbox smoke + canary
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\_env_staging_from_fly.ps1
python .\scripts\canary_smoke.py
```

Optional provider-specific smokes:
- `python .\scripts\momo_smoke.py`
- `python .\scripts\thunes_smoke.py`

## 4) Verify webhook signature + event linking
- Trigger a payout in staging.
- Verify webhook request has valid signature (HTTP 200).
- Confirm event linked to payout in admin:
  ```
  GET /v1/admin/mobile-money/trace?transaction_id=<tx_id>
  ```

## 5) Promote to prod
- Set provider flag + real secrets in prod:
  ```powershell
  fly secrets set --app nepxy-prod TMONEY_ENABLED="true"
  ```
- Deploy: `fly deploy -c fly.prod.toml --app nepxy-prod --remote-only`
- Run prod smoke: `powershell -ExecutionPolicy Bypass -File .\scripts\prod_smoke.ps1`

## Notes
- Keep provider disabled in prod until staging canary is green.
- Use provider readiness endpoint to confirm missing keys:
  `GET /v1/admin/provider-readiness`
