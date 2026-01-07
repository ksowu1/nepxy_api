

# scripts/run_api.ps1
# Run NepXy API in dev mode on Windows, avoiding httptools on Python 3.13
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\run_api.ps1

$ErrorActionPreference = "Stop"

# Always run from project root
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Split-Path -Parent $ROOT
Set-Location $ROOT

# Use h11 to avoid httptools issues on Py3.13
uvicorn main:app `
  --host 0.0.0.0 `
  --port 8001 `
  --reload `
  --http h11 `
  --reload-exclude ".venv/*" `
  --reload-exclude "venv/*"
