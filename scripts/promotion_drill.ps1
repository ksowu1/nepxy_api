<#[
Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\promotion_drill.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\promotion_drill.ps1 -DryRun
#>

param(
    [string]$StagingApp = "nepxy-staging",
    [string]$ProdApp = "nepxy-prod",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Require-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "Missing required command: $name"
        exit 2
    }
}

function Step([string]$label, [ScriptBlock]$block) {
    Write-Host "==> $label"
    if ($DryRun) {
        Write-Host "(dry-run)"
        return
    }
    $global:LASTEXITCODE = 0
    & $block
    if (-not $?) {
        Write-Error "Step failed: $label"
        exit 1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Step failed: $label"
        exit $LASTEXITCODE
    }
}

function Fail([string]$message) {
    Write-Error $message
    exit 1
}

Require-Command "fly"
Require-Command "python"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$stagingEnvScript = Join-Path $repoRoot "scripts\_env_staging_from_fly.ps1"
$stagingBackupScript = Join-Path $repoRoot "scripts\db_backup_staging.ps1"
$prodSmokeScript = Join-Path $repoRoot "scripts\prod_smoke.ps1"
$prodConfig = Join-Path $repoRoot "fly.prod.toml"
$backupDir = Join-Path $repoRoot "backups"

if (-not (Test-Path $stagingEnvScript)) { Fail "Missing $stagingEnvScript" }
if (-not (Test-Path $stagingBackupScript)) { Fail "Missing $stagingBackupScript" }
if (-not (Test-Path $prodSmokeScript)) { Fail "Missing $prodSmokeScript" }
if (-not (Test-Path $prodConfig)) { Fail "Missing $prodConfig" }

Step "Load staging env from Fly (dot-source)" {
    . $stagingEnvScript
    $global:LASTEXITCODE = 0
}

if (-not $env:STAGING_BASE_URL -or -not $env:STAGING_GATE_KEY) {
    Write-Error "Staging env not loaded correctly. Missing STAGING_BASE_URL or STAGING_GATE_KEY."
    exit 1
}

Write-Host ("Staging env check: base_url=" + $env:STAGING_BASE_URL)
Write-Host ("Secrets lengths: gate={0} user_email={1} admin_email={2} tmoney={3} thunes={4} bootstrap={5}" -f `
    ($env:STAGING_GATE_KEY.Length), `
    ($env:STAGING_USER_EMAIL.Length), `
    ($env:STAGING_ADMIN_EMAIL.Length), `
    ($env:TMONEY_WEBHOOK_SECRET.Length), `
    ($env:THUNES_WEBHOOK_SECRET.Length), `
    ($env:BOOTSTRAP_ADMIN_SECRET.Length)
)

Step "Run staging canary (must be green)" {
    python (Join-Path $repoRoot "scripts\canary_smoke.py")
}

Step "Staging DB backup" {
    powershell -ExecutionPolicy Bypass -File $stagingBackupScript
}

Write-Host "==> Ensure prod app exists"
if ($DryRun) {
    Write-Host "(dry-run) fly status --app $ProdApp"
} else {
    & fly status --app $ProdApp | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Prod app not found. Create it with:"
        Write-Host "  fly apps create $ProdApp"
        Write-Host "  fly postgres create --name ${ProdApp}-db"
        Write-Host "  fly postgres attach --app $ProdApp ${ProdApp}-db"
        Fail "Prod app missing. Create it and rerun."
    }
}

Step "Validate fly.prod.toml" {
    fly config validate -c $prodConfig
}

Step "Deploy to prod (remote-only)" {
    fly deploy -c $prodConfig --app $ProdApp --remote-only
}

Step "Run prod smoke" {
    if (-not $env:BASE_URL) { $env:BASE_URL = "https://nepxy-prod.fly.dev" }
    if (-not $env:SMOKE_EMAIL -or -not $env:SMOKE_PASSWORD) {
        Write-Error "Missing SMOKE_EMAIL or SMOKE_PASSWORD for prod smoke. Set them and rerun."
        exit 1
    }
    powershell -ExecutionPolicy Bypass -File $prodSmokeScript
}

Write-Host "==> Rollback (manual)"
Write-Host "1) List releases: fly releases --app $ProdApp"
Write-Host "2) Roll back: fly deploy --image <digest> --app $ProdApp"
Write-Host ("Backup folder: " + $backupDir)
