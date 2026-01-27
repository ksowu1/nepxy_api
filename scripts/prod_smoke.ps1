<# 
Usage:
  $env:BASE_URL="https://nepxy.example.com"
  $env:SMOKE_EMAIL="user@example.com"
  $env:SMOKE_PASSWORD="password123"
  $env:STAGING_GATE_KEY="optional"
  .\scripts\prod_smoke.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Env([string]$name) {
    if (-not ${env:$name}) {
        Write-Error "Missing required env var: $name"
        exit 2
    }
}

Require-Env "BASE_URL"
Require-Env "SMOKE_EMAIL"
Require-Env "SMOKE_PASSWORD"

$baseUrl = $env:BASE_URL.TrimEnd("/")
$headers = @{}
if ($env:STAGING_GATE_KEY) {
    $headers["X-Staging-Key"] = $env:STAGING_GATE_KEY
}

function Invoke-Health([string]$path) {
    $resp = Invoke-WebRequest -Method GET -Uri ($baseUrl + $path) -Headers $headers -UseBasicParsing
    if ($resp.StatusCode -ne 200) {
        Write-Error "Health check failed: $path -> $($resp.StatusCode)"
        exit 1
    }
}

Invoke-Health "/health"
Invoke-Health "/readyz"

$loginBody = @{
    email = $env:SMOKE_EMAIL
    password = $env:SMOKE_PASSWORD
} | ConvertTo-Json

$loginResp = Invoke-WebRequest -Method POST -Uri ($baseUrl + "/v1/auth/login") -Headers $headers -ContentType "application/json" -Body $loginBody -UseBasicParsing
if ($loginResp.StatusCode -ne 200) {
    Write-Error "Login failed: $($loginResp.StatusCode) $($loginResp.Content)"
    exit 1
}

$requestId = $loginResp.Headers["X-Request-ID"]
if ($requestId) {
    Write-Host "Login X-Request-ID: $requestId"
}

Write-Host "Prod smoke OK"
