param()

$ErrorActionPreference = "Stop"

if (-not $env:BASE_URL) {
    if ($env:NEPXY_BASE_URL) {
        $env:BASE_URL = $env:NEPXY_BASE_URL
    } else {
        $env:BASE_URL = "http://127.0.0.1:8001"
    }
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

if (-not $env:USER_EMAIL) {
    $env:USER_EMAIL = Read-NonEmpty "USER email"
}
if (-not $env:USER_PASSWORD) {
    $secure = Read-Host "USER password" -AsSecureString
    $env:USER_PASSWORD = SecureToPlain $secure
}
if (-not $env:ADMIN_EMAIL) {
    $env:ADMIN_EMAIL = Read-NonEmpty "ADMIN email"
}
if (-not $env:ADMIN_PASSWORD) {
    $secure = Read-Host "ADMIN password" -AsSecureString
    $env:ADMIN_PASSWORD = SecureToPlain $secure
}

python scripts/smoke_dev.py
exit $LASTEXITCODE
