

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load local env if present
if (Test-Path ".\scripts\env.ps1") { . .\scripts\env.ps1 }

# Start payout worker
python -m app.workers.run_payout_worker

