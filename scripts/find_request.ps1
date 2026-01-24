# scripts/find_request.ps1
param(
    [Parameter(Mandatory = $true)]
    [string]$RequestId,
    [string]$App = "nepxy-staging"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RequestId.Trim()) {
    throw "RequestId is required."
}

Write-Host "Streaming Fly logs for request_id=$RequestId (app=$App)..."
fly logs -a $App | Select-String -Pattern $RequestId
