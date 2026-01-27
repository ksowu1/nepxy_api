param(
  [Parameter(Mandatory=$true)][string]$RequestId,
  [string]$App = "nepxy-staging"
)

if (-not $RequestId) {
  Write-Host "Usage: .\\scripts\\find_request.ps1 -RequestId <id> [-App nepxy-staging]"
  exit 1
}

Write-Host "Searching Fly logs for request_id=$RequestId (app=$App)..."
fly logs --app $App --no-tail | Select-String -Pattern "request_id=$RequestId"
