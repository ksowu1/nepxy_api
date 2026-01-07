


# ============================
# Nepxy PowerShell Cookbook
# login, wallets, activity, cash-in, cash-out, payout status, webhooks, admin ops, worker metrics
# ============================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---- 0) Config ----
# NOTE: keep this PowerShell 5.1 compatible (no ?? operator)
if ($env:NEPXY_BASE -and ($env:NEPXY_BASE.Trim() -ne "")) {
  $script:NEPXY_BASE = $env:NEPXY_BASE.Trim().TrimEnd("/")
} else {
  $script:NEPXY_BASE = "http://127.0.0.1:8001"
}
$script:NEPXY_TOKEN = $null

function Set-NepxyBaseUrl {
  param([Parameter(Mandatory=$true)][string]$BaseUrl)
  $script:NEPXY_BASE = $BaseUrl.TrimEnd("/")
  $script:NEPXY_BASE
}

function Set-NepxyToken {
  param([Parameter(Mandatory=$true)][string]$Token)
  $script:NEPXY_TOKEN = $Token
  $script:NEPXY_TOKEN
}

function New-IdempotencyKey { [guid]::NewGuid().ToString() }

function Invoke-Nepxy {
  <#
    Wrapper around Invoke-RestMethod:
      - Adds Authorization header (if token set)
      - Adds Idempotency-Key if provided
      - Supports JSON body (hashtable/pscustomobject)
  #>
  param(
    [Parameter(Mandatory=$true)][ValidateSet("GET","POST","PUT","PATCH","DELETE")][string]$Method,
    [Parameter(Mandatory=$true)][string]$Path,
    [object]$JsonBody = $null,
    [string]$Token = $script:NEPXY_TOKEN,
    [string]$IdempotencyKey = $null,
    [hashtable]$ExtraHeaders = @{}
  )

  $uri = "$($script:NEPXY_BASE)$Path"
  $headers = @{}
  if ($Token) { $headers["Authorization"] = "Bearer $Token" }
  if ($IdempotencyKey) { $headers["Idempotency-Key"] = $IdempotencyKey }
  foreach ($k in $ExtraHeaders.Keys) { $headers[$k] = $ExtraHeaders[$k] }

  if ($null -ne $JsonBody) {
    $body = $JsonBody | ConvertTo-Json -Depth 12
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body $body
  } else {
    return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
  }
}

# ---- 1) Login (get access token) ----
function Get-NepxyToken {
  param(
    [string]$Email = "admin@nexapay.io",
    [string]$Password = "<REDACTED>",
    [string]$BaseUrl = $script:NEPXY_BASE
  )
  $old = $script:NEPXY_BASE
  $script:NEPXY_BASE = $BaseUrl.TrimEnd("/")
  try {
    $resp = Invoke-Nepxy -Method POST -Path "/v1/auth/login" -JsonBody @{ email=$Email; password=$Password } -Token $null
    Set-NepxyToken -Token $resp.access_token | Out-Null
    return $resp.access_token
  } finally {
    $script:NEPXY_BASE = $old
  }
}

# ---- 2) Wallets ----
function Get-MyWallets {
  param([string]$Token = $script:NEPXY_TOKEN)
  (Invoke-Nepxy -Method GET -Path "/v1/wallets" -Token $Token).wallets
}

function Get-WalletBalance {
  param(
    [Parameter(Mandatory=$true)][string]$WalletId,
    [string]$Token = $script:NEPXY_TOKEN
  )
  Invoke-Nepxy -Method GET -Path "/v1/wallets/$WalletId/balance" -Token $Token
}

function Get-WalletActivity {
  param(
    [Parameter(Mandatory=$true)][string]$WalletId,
    [int]$Limit = 20,
    [string]$Token = $script:NEPXY_TOKEN
  )
  Invoke-Nepxy -Method GET -Path "/v1/wallets/$WalletId/activity?limit=$Limit" -Token $Token
}

# ---- 3) P2P transfer (wallet-to-wallet) ----
function New-P2PTransfer {
  param(
    [Parameter(Mandatory=$true)][string]$FromWalletId,
    [Parameter(Mandatory=$true)][string]$ToWalletId,
    [Parameter(Mandatory=$true)][int]$AmountCents,
    [string]$Memo = "p2p",
    [string]$Token = $script:NEPXY_TOKEN
  )
  $idem = New-IdempotencyKey
  Invoke-Nepxy -Method POST -Path "/v1/payments/p2p" -Token $Token -IdempotencyKey $idem -JsonBody @{
    from_wallet_id=$FromWalletId
    to_wallet_id=$ToWalletId
    amount_cents=$AmountCents
    memo=$Memo
  }
}

# ---- 4) CASH-IN (Mobile Money)  -> POST /v1/cash-in/mobile-money ----
function New-CashInMobileMoney {
  param(
    [Parameter(Mandatory=$true)][string]$WalletId,
    [Parameter(Mandatory=$true)][int]$AmountCents,
    [string]$Country = "TG",          # "TG","BJ","BF","ML"
    [ValidateSet("TMONEY","FLOOZ","MOMO")][string]$Provider = "TMONEY",
    [string]$PhoneE164 = "+22890009911",
    [string]$ProviderRef = $null,
    [string]$Token = $script:NEPXY_TOKEN
  )
  $idem = New-IdempotencyKey
  if (-not $ProviderRef) { $ProviderRef = "cashin-" + (New-IdempotencyKey) }

  $resp = Invoke-Nepxy -Method POST -Path "/v1/cash-in/mobile-money" -Token $Token -IdempotencyKey $idem -JsonBody @{
    wallet_id    = $WalletId
    amount_cents = $AmountCents
    country      = $Country
    provider_ref = $ProviderRef
    provider     = $Provider
    phone_e164   = $PhoneE164
  }

  [pscustomobject]@{
    transaction_id  = $resp.transaction_id
    provider_ref    = $ProviderRef
    idempotency_key = $idem
    raw             = $resp
  }
}

# ---- 5) CASH-OUT (Mobile Money) -> POST /v1/cash-out/mobile-money ----
function New-CashOutMobileMoney {
  param(
    [Parameter(Mandatory=$true)][string]$WalletId,
    [Parameter(Mandatory=$true)][int]$AmountCents,
    [string]$Country = "TG",
    [ValidateSet("TMONEY","FLOOZ","MOMO")][string]$Provider = "TMONEY",
    [string]$PhoneE164 = "+22890009911",
    [string]$ProviderRef = $null,
    [string]$Token = $script:NEPXY_TOKEN
  )
  $idem = New-IdempotencyKey
  if (-not $ProviderRef) { $ProviderRef = "cashout-" + (New-IdempotencyKey) }

  $resp = Invoke-Nepxy -Method POST -Path "/v1/cash-out/mobile-money" -Token $Token -IdempotencyKey $idem -JsonBody @{
    wallet_id    = $WalletId
    amount_cents = $AmountCents
    country      = $Country
    provider_ref = $ProviderRef
    provider     = $Provider
    phone_e164   = $PhoneE164
  }

  [pscustomobject]@{
    transaction_id  = $resp.transaction_id
    provider_ref    = $ProviderRef
    idempotency_key = $idem
    raw             = $resp
  }
}

# ---- 6) Payout status ----
function Get-PayoutStatus {
  param(
    [Parameter(Mandatory=$true)][string]$TransactionId,
    [string]$Token = $script:NEPXY_TOKEN
  )
  Invoke-Nepxy -Method GET -Path "/v1/payouts/$TransactionId" -Token $Token
}

# ---- 7) Webhooks (sandbox) ----
function Send-TmoneyWebhook {
  param(
    [Parameter(Mandatory=$true)][string]$ProviderRef,
    [ValidateSet("SUCCESS","FAILED","SENT","PENDING")][string]$Status = "SUCCESS"
  )
  Invoke-Nepxy -Method POST -Path "/v1/webhooks/tmoney" -Token $null -JsonBody @{
    provider_ref = $ProviderRef
    status       = $Status
  }
}

# NOTE: When you add /v1/webhooks/flooz and /v1/webhooks/momo later,
# duplicate this pattern (or create a generic Send-ProviderWebhook).

# ---- 8) Admin ops (optional) ----
function Set-PayoutConfirmed_Admin {
  param(
    [Parameter(Mandatory=$true)][string]$TransactionId,
    [string]$Token = $script:NEPXY_TOKEN
  )
  Invoke-Nepxy -Method POST -Path "/v1/admin/mobile-money/payouts/$TransactionId/confirmed" -Token $Token
}

# ---- 9) Worker metrics (debug) ----
# Requires: GET /v1/admin/mobile-money/payouts/metrics?stale_seconds=60
function Get-PayoutWorkerMetrics {
  param(
    [int]$StaleSeconds = 60,
    [string]$Token = $script:NEPXY_TOKEN
  )
  Invoke-Nepxy -Method GET -Path "/v1/admin/mobile-money/payouts/metrics?stale_seconds=$StaleSeconds" -Token $Token
}

function Get-PayoutWorkerMetricsPretty {
  param(
    [int]$StaleSeconds = 60,
    [string]$Token = $script:NEPXY_TOKEN
  )

  $m = Get-PayoutWorkerMetrics -StaleSeconds $StaleSeconds -Token $Token

  "`n== COUNTS =="
  $m | Select-Object stale_seconds, now, pending_total, pending_due, pending_not_due, sent_total, sent_due, sent_stale_due, failed_24h, confirmed_24h | Format-List

  "`n== OLDEST PENDING =="
  if (-not $m.oldest_pending -or $m.oldest_pending.Count -eq 0) { "none" } else {
    $m.oldest_pending | Select-Object transaction_id, external_ref, provider, attempt_count, next_retry_at, created_at, last_error | Format-Table -AutoSize
  }

  "`n== OLDEST SENT =="
  if (-not $m.oldest_sent -or $m.oldest_sent.Count -eq 0) { "none" } else {
    $m.oldest_sent | Select-Object transaction_id, external_ref, provider, attempt_count, next_retry_at, seconds_since_last_touch, last_error | Format-Table -AutoSize
  }
}

# ============================
# Quickstart (copy/paste)
# ============================
# Set-NepxyBaseUrl "http://127.0.0.1:8001"
# $TOKEN = Get-NepxyToken -Email "admin@nexapay.io" -Password "<REDACTED>"
# $wallets = Get-MyWallets
# $WALLET_ID = $wallets[0].wallet_id
# Get-WalletBalance -WalletId $WALLET_ID
# $out = New-CashOutMobileMoney -WalletId $WALLET_ID -AmountCents 1000 -Provider "TMONEY" -Country "TG"
# $tx = $out.transaction_id
# Get-PayoutStatus -TransactionId $tx | Format-List
# # IMPORTANT: webhook must use the stored provider_ref from payout status:
# $pref = (Get-PayoutStatus -TransactionId $tx).provider_ref
# Send-TmoneyWebhook -ProviderRef $pref -Status "SUCCESS"
# Get-PayoutStatus -TransactionId $tx | Format-List

