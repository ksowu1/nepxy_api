param()

$ErrorActionPreference = "Stop"

$base = $env:NEPXY_BASE_URL
if (-not $base) {
    $base = "http://127.0.0.1:8001"
}

$stagingGate = $env:STAGING_GATE_KEY
if ($stagingGate -and $stagingGate.Trim().Length -gt 0) {
    Write-Host "Using staging gate header"
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

function SecureToPlain([Security.SecureString]$Secure) {
    return [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    )
}

function Invoke-Api([string]$Method, [string]$Uri, [hashtable]$Headers, [string]$Body) {
    try {
        if ($Body) {
            return Invoke-WebRequest -Method $Method -Uri $Uri -Headers $Headers -Body $Body -ContentType "application/json"
        }
        return Invoke-WebRequest -Method $Method -Uri $Uri -Headers $Headers
    } catch {
        $resp = $_.Exception.Response
        if ($resp -and $resp.GetResponseStream()) {
            $reader = New-Object IO.StreamReader($resp.GetResponseStream())
            $bodyText = $reader.ReadToEnd()
            Write-Host "HTTP $($resp.StatusCode) $($resp.StatusDescription)" -ForegroundColor Red
            Write-Host $bodyText
        } else {
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
        throw
    }
}

function AuthHeaders([string]$Token, [string]$Idem) {
    $h = @{ Authorization = "Bearer $Token" }
    if ($stagingGate -and $stagingGate.Trim().Length -gt 0) {
        $h["X-Staging-Key"] = $stagingGate.Trim()
    }
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
$userPassPlain = SecureToPlain $userPass

Write-Host "Admin credentials" -ForegroundColor Cyan
$adminEmail = Read-NonEmpty "Admin email"
$adminPass = Read-Host "Admin password" -AsSecureString
$adminPassPlain = SecureToPlain $adminPass

$loginUserBody = @{ email = $userEmail; password = $userPassPlain } | ConvertTo-Json -Depth 5
$loginAdminBody = @{ email = $adminEmail; password = $adminPassPlain } | ConvertTo-Json -Depth 5

$loginHeaders = @{}
if ($stagingGate -and $stagingGate.Trim().Length -gt 0) {
    $loginHeaders["X-Staging-Key"] = $stagingGate.Trim()
}

$userLogin = Invoke-Api -Method "Post" -Uri "$base/v1/auth/login" -Headers $loginHeaders -Body $loginUserBody
$adminLogin = Invoke-Api -Method "Post" -Uri "$base/v1/auth/login" -Headers $loginHeaders -Body $loginAdminBody

$token = ($userLogin.Content | ConvertFrom-Json).access_token
$adminToken = ($adminLogin.Content | ConvertFrom-Json).access_token

if (-not $token) { throw "Missing user access_token." }
if (-not $adminToken) { throw "Missing admin access_token." }

$walletsResp = Invoke-Api -Method "Get" -Uri "$base/v1/wallets" -Headers (AuthHeaders -Token $token -Idem $null) -Body $null
$walletsObj = $walletsResp.Content | ConvertFrom-Json
$wallets = @()
if ($walletsObj.wallets) {
    $wallets = $walletsObj.wallets
} elseif ($walletsObj -is [System.Array]) {
    $wallets = $walletsObj
}
if (-not $wallets -or $wallets.Count -eq 0) {
    throw "No wallets returned."
}
$walletId = $wallets[0].wallet_id
if (-not $walletId) {
    $walletId = $wallets[0].id
}
if (-not $walletId) {
    throw "Could not determine wallet_id."
}

$cashInBody = @{
    wallet_id = $walletId
    amount_cents = 2000
    country = "TG"
    provider = "TMONEY"
    phone_e164 = "+22890009911"
} | ConvertTo-Json -Depth 5

Invoke-Api -Method "Post" -Uri "$base/v1/cash-in/mobile-money" -Headers (AuthHeaders -Token $token -Idem (New-IdemKey)) -Body $cashInBody | Out-Null

$cashOutBody = @{
    wallet_id = $walletId
    amount_cents = 100
    country = "TG"
    provider = "TMONEY"
    phone_e164 = "+22890009911"
} | ConvertTo-Json -Depth 5

$cashOutResp = Invoke-Api -Method "Post" -Uri "$base/v1/cash-out/mobile-money" -Headers (AuthHeaders -Token $token -Idem (New-IdemKey)) -Body $cashOutBody
$cashOutObj = $cashOutResp.Content | ConvertFrom-Json
$tx = $cashOutObj.transaction_id
if (-not $tx) { throw "Missing transaction_id." }

$payoutResp = Invoke-Api -Method "Get" -Uri "$base/v1/payouts/$tx" -Headers (AuthHeaders -Token $token -Idem $null) -Body $null
$payoutObj = $payoutResp.Content | ConvertFrom-Json
$externalRef = $payoutObj.external_ref
if (-not $externalRef) { throw "Missing external_ref." }

$payloadObj = @{ external_ref = $externalRef; status = "SUCCESS" }
$payloadJson = $payloadObj | ConvertTo-Json -Compress
$payloadBytes = [Text.Encoding]::UTF8.GetBytes($payloadJson)
$sig = Sign-Tmoney -BodyBytes $payloadBytes -Secret $env:TMONEY_WEBHOOK_SECRET

$webhookHeaders = @{ "Content-Type" = "application/json"; "X-Signature" = $sig }
if ($stagingGate -and $stagingGate.Trim().Length -gt 0) {
    $webhookHeaders["X-Staging-Key"] = $stagingGate.Trim()
}
Invoke-Api -Method "Post" -Uri "$base/v1/webhooks/tmoney" -Headers $webhookHeaders -Body $payloadJson | Out-Null

$eventsResp = Invoke-Api -Method "Get" -Uri "$base/v1/admin/webhooks/events?limit=50&external_ref=$externalRef&provider=TMONEY" -Headers (AuthHeaders -Token $adminToken -Idem $null) -Body $null
$eventsObj = $eventsResp.Content | ConvertFrom-Json
$eventList = $eventsObj.events
if (-not $eventList -or $eventList.Count -eq 0) { throw "No webhook events found." }

$valid = $eventList | Where-Object { $_.signature_valid -eq $true }
$picked = $null
if ($valid -and $valid.Count -gt 0) {
    $picked = $valid[0]
} else {
    $picked = $eventList[0]
}
if (-not $picked.id) { throw "No event id for replay." }

Invoke-Api -Method "Post" -Uri "$base/v1/admin/webhooks/events/$($picked.id)/replay" -Headers (AuthHeaders -Token $adminToken -Idem $null) -Body $null | Out-Null

$finalPayoutResp = Invoke-Api -Method "Get" -Uri "$base/v1/payouts/$tx" -Headers (AuthHeaders -Token $token -Idem $null) -Body $null
$finalPayout = $finalPayoutResp.Content | ConvertFrom-Json

$adminEventsResp = Invoke-Api -Method "Get" -Uri "$base/v1/admin/mobile-money/payouts/$tx/webhook-events?limit=50" -Headers (AuthHeaders -Token $adminToken -Idem $null) -Body $null
$adminEvents = $adminEventsResp.Content | ConvertFrom-Json

Write-Host "payout_status=$($finalPayout.status)"
Write-Host "admin_payout_webhook_events:"
$adminEvents | ConvertTo-Json -Depth 10
