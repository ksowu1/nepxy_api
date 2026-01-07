# NepXy PowerShell Cookbook

A copy/paste friendly set of PowerShell helpers for local Nepxy API testing:
login, wallets, activity, cash-in, cash-out, payout status, webhooks, admin ops, and worker metrics.

## Quickstart

1) Start the API

```powershell
python -m uvicorn main:app --port 8001 --reload --reload-exclude .venv
```

2) Load the cookbook (dot-source)

```powershell
# Works in Windows PowerShell 5.1 and PowerShell 7+
. .\Nepxy-Cookbook.ps1

# If you kept an "updated" filename instead:
# . .\Nepxy-Cookbook.updated.ps1
```

3) Login + pick a wallet

```powershell
Set-NepxyBaseUrl "http://127.0.0.1:8001"

$TOKEN = Get-NepxyToken -Email "admin@nexapay.io" -Password "<YOUR_PASSWORD>"
$wallets = Get-MyWallets
$WALLET_ID = $wallets[0].wallet_id

Get-WalletBalance -WalletId $WALLET_ID
```

4) Cash-out -> confirm via sandbox webhook

```powershell
$out = New-CashOutMobileMoney -WalletId $WALLET_ID -AmountCents 1000 -Provider "TMONEY" -Country "TG"
$tx = $out.transaction_id

# Fetch stored ref then send webhook (IMPORTANT: use stored provider_ref / external_ref)
$p = Get-PayoutStatus -TransactionId $tx
Send-TmoneyWebhook -ExternalRef $p.external_ref -Status "SUCCESS"

Get-PayoutStatus -TransactionId $tx | Format-List
```

## Worker Metrics (debug)

If you added the endpoint:

`GET /v1/admin/mobile-money/payouts/metrics?stale_seconds=60`

then you can quickly see what's stuck in PENDING/SENT and what's getting confirmed/failed.

```powershell
$TOKEN = Get-NepxyToken -Email "admin@nexapay.io" -Password "<YOUR_PASSWORD>"
Get-PayoutWorkerMetricsPretty -StaleSeconds 60
```

## Notes

- For idempotent endpoints, the cookbook generates a new `Idempotency-Key` automatically.
- Donâ€™t hardcode passwords in real use. Prefer `$env:NEXA_EMAIL`, `$env:NEXA_PASSWORD`, or `Get-Credential`.

