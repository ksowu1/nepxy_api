param()

$ErrorActionPreference = "Stop"

$base = $env:NEPXY_BASE_URL
if (-not $base) {
    $base = "http://127.0.0.1:8001"
}

if (-not $env:TMONEY_WEBHOOK_SECRET) {
    $env:TMONEY_WEBHOOK_SECRET = "dev_secret_tmoney"
}

function Read-NonEmpty([string]$Prompt) {
    while ($true) {
        $value = Read-Host $Prompt
        if ($value -and $value.Trim().Length -gt 0) {
            return $value.Trim()
        }
        Write-Host "Value required." -ForegroundColor Yellow
    }
}

function Login([string]$Email, [string]$Password) {
    $body = @{
        email = $Email
        password = $Password
    } | ConvertTo-Json -Depth 5

    $resp = Invoke-RestMethod -Method Post -Uri "$base/v1/auth/login" -ContentType "application/json" -Body $body
    return $resp.access_token
}

function AuthHeaders([string]$Token, [string]$Idem) {
    $h = @{ Authorization = "Bearer $Token" }
    if ($Idem) {
        $h["Idempotency-Key"] = $Idem
    }
    return $h
}

function New-IdemKey() {
    return ("idem-" + [Guid]::NewGuid().ToString("N"))
}

function Sign-Tmoney([byte[]]$BodyBytes, [string]$Secret) {
    $hmac = New-Object System.Security.Cryptography.HMACSHA256
    $hmac.Key = [Text.Encoding]::UTF8.GetBytes($Secret)
    $hash = $hmac.ComputeHash($BodyBytes)
    $hex = ($hash | ForEach-Object { $_.ToString("x2") }) -join ""
    return "sha256=$hex"
}

Write-Host "User credentials" -ForegroundColor Cyan
$userEmail = Read-NonEmpty "User email"
$userPass = Read-Host "User password" -AsSecureString
$userPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($userPass))

Write-Host "Admin credentials" -ForegroundColor Cyan
$adminEmail = Read-NonEmpty "Admin email"
$adminPass = Read-Host "Admin password" -AsSecureString
$adminPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminPass))

$token = Login -Email $userEmail -Password $userPassPlain
$adminToken = Login -Email $adminEmail -Password $adminPassPlain

$walletsResp = Invoke-RestMethod -Method Get -Uri "$base/v1/wallets" -Headers (AuthHeaders -Token $token -Idem $null)
$wallets = @()
if ($walletsResp.wallets) {
    $wallets = $walletsResp.wallets
} elseif ($walletsResp -is [System.Array]) {
    $wallets = $walletsResp
}

if (-not $wallets -or $wallets.Count -eq 0) {
    throw "No wallets returned for user."
}

$walletId = $wallets[0].wallet_id
if (-not $walletId) {
    $walletId = $wallets[0].id
}
if (-not $walletId) {
    throw "Could not determine wallet_id."
}

$cashInIdem = New-IdemKey
$cashInBody = @{
    wallet_id = $walletId
    amount_cents = 2000
    country = "TG"
    provider = "TMONEY"
    phone_e164 = "+22890009911"
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "$base/v1/cash-in/mobile-money" -Headers (AuthHeaders -Token $token -Idem $cashInIdem) -ContentType "application/json" -Body $cashInBody | Out-Null

$cashOutIdem = New-IdemKey
$cashOutBody = @{
    wallet_id = $walletId
    amount_cents = 100
    country = "TG"
    provider = "TMONEY"
    phone_e164 = "+22890009911"
} | ConvertTo-Json -Depth 5

$cashOutResp = Invoke-RestMethod -Method Post -Uri "$base/v1/cash-out/mobile-money" -Headers (AuthHeaders -Token $token -Idem $cashOutIdem) -ContentType "application/json" -Body $cashOutBody
$tx = $cashOutResp.transaction_id
if (-not $tx) {
    throw "Missing transaction_id from cash-out response."
}

$payout = Invoke-RestMethod -Method Get -Uri "$base/v1/payouts/$tx" -Headers (AuthHeaders -Token $token -Idem $null)
$externalRef = $payout.external_ref
if (-not $externalRef) {
    throw "Missing external_ref from payout response."
}

$payloadObj = @{ external_ref = $externalRef; status = "SUCCESS" }
$payloadJson = $payloadObj | ConvertTo-Json -Compress
$payloadBytes = [Text.Encoding]::UTF8.GetBytes($payloadJson)
$sig = Sign-Tmoney -BodyBytes $payloadBytes -Secret $env:TMONEY_WEBHOOK_SECRET

$headers = @{ "Content-Type" = "application/json"; "X-Signature" = $sig }
Invoke-RestMethod -Method Post -Uri "$base/v1/webhooks/tmoney" -Headers $headers -Body $payloadBytes | Out-Null

$events = Invoke-RestMethod -Method Get -Uri "$base/v1/admin/webhooks/events?limit=50&external_ref=$externalRef" -Headers (AuthHeaders -Token $adminToken -Idem $null)
$eventList = $events.events
if (-not $eventList) {
    throw "No webhook events found for external_ref."
}

$valid = $eventList | Where-Object { $_.signature_valid -eq $true }
$picked = $null
if ($valid -and $valid.Count -gt 0) {
    $picked = $valid[0]
} else {
    $picked = $eventList[0]
}

if (-not $picked -or -not $picked.id) {
    throw "No webhook event id available for replay."
}

$replay = Invoke-RestMethod -Method Post -Uri "$base/v1/admin/webhooks/events/$($picked.id)/replay" -Headers (AuthHeaders -Token $adminToken -Idem $null)

$finalPayout = Invoke-RestMethod -Method Get -Uri "$base/v1/payouts/$tx" -Headers (AuthHeaders -Token $token -Idem $null)

Write-Host "tx=$tx"
Write-Host "external_ref=$externalRef"
Write-Host "replay_response:"; ($replay | ConvertTo-Json -Depth 10)
Write-Host "final_payout:"; ($finalPayout | ConvertTo-Json -Depth 10)
