param()

function Mask-Value([string]$Value) {
    if (-not $Value) { return "<empty>" }
    if ($Value.Length -le 4) { return ("*" * $Value.Length) }
    return ("*" * ($Value.Length - 4)) + $Value.Substring($Value.Length - 4)
}

$issueOutput = & fly ssh issue --app nepxy-staging 2>&1
if ($LASTEXITCODE -ne 0) {
    $issueOutput = & fly ssh issue -a nepxy-staging 2>&1
}

$secretsOutput = & fly secrets list --app nepxy-staging 2>&1
if ($LASTEXITCODE -ne 0) {
    $secretsOutput = & fly secrets list -a nepxy-staging 2>&1
}

$cmd = 'sh -lc ''echo STAGING_GATE_KEY="$STAGING_GATE_KEY"; echo STAGING_USER_EMAIL="$STAGING_USER_EMAIL"; echo STAGING_USER_PASSWORD="$STAGING_USER_PASSWORD"; echo STAGING_ADMIN_EMAIL="$STAGING_ADMIN_EMAIL"; echo STAGING_ADMIN_PASSWORD="$STAGING_ADMIN_PASSWORD"; echo USER_EMAIL="$USER_EMAIL"; echo USER_PASSWORD="$USER_PASSWORD"; echo ADMIN_EMAIL="$ADMIN_EMAIL"; echo ADMIN_PASSWORD="$ADMIN_PASSWORD"; echo TMONEY_WEBHOOK_SECRET="$TMONEY_WEBHOOK_SECRET"; echo THUNES_WEBHOOK_SECRET="$THUNES_WEBHOOK_SECRET"; echo BOOTSTRAP_ADMIN_SECRET="$BOOTSTRAP_ADMIN_SECRET"'''
$flyOutput = & fly ssh console --app nepxy-staging -C $cmd 2>&1
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0 -and ($flyOutput -join "`n") -match "unknown flag: --app") {
    $flyOutput = & fly ssh console -a nepxy-staging -C $cmd 2>&1
    $exitCode = $LASTEXITCODE
}
$rawOutput = $flyOutput -join "`n"

if (-not $rawOutput) {
    Write-Host "Failed to read env from Fly (nepxy-staging). Exit code: $exitCode. Run: fly status --app nepxy-staging" -ForegroundColor Red
    $rawOutput = ""
}

$envMap = @{}
foreach ($line in ($rawOutput -split "`n")) {
    $trimmed = $line.Trim()
    if (-not $trimmed) { continue }
    $m = [regex]::Match($trimmed, '^([A-Z0-9_]+)=(.*)$')
    if (-not $m.Success) { continue }
    $key = $m.Groups[1].Value
    $value = $m.Groups[2].Value
    if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    $value = $value.Trim()
    $envMap[$key] = $value
}

$requiredKeys = @(
    "STAGING_GATE_KEY",
    "USER_EMAIL",
    "USER_PASSWORD",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "TMONEY_WEBHOOK_SECRET",
    "BOOTSTRAP_ADMIN_SECRET"
)
$missing = @()
$loadedLocal = $false
foreach ($k in $requiredKeys) {
    if (-not $envMap.ContainsKey($k) -or -not $envMap[$k]) {
        $missing += $k
    }
}
if ($missing.Count -gt 0) {
    if ($secretsOutput) {
        $secretsText = $secretsOutput -join "`n"
        $missingNames = @()
        foreach ($k in $requiredKeys) {
            if ($secretsText -notmatch ("(^|\\s)" + [regex]::Escape($k) + "($|\\s)")) {
                $missingNames += $k
            }
        }
        if ($missingNames.Count -gt 0) {
            Write-Host ("Fly secrets missing (names only, no values): " + ($missingNames -join ", ")) -ForegroundColor Yellow
        }
    }

    $localPath = Join-Path $PSScriptRoot "_env_staging_local.ps1"
    if (Test-Path $localPath) {
        . $localPath
        Write-Host "Loaded staging secrets from local overrides file."
        $loadedLocal = $true
    } else {
        Write-Host ("Missing required values from Fly: " + ($missing -join ", ")) -ForegroundColor Yellow
        Write-Host ("Fly does not reveal secret values. Create " + $localPath + " with env exports, then re-run.") -ForegroundColor Yellow
        Write-Host "Example:" -ForegroundColor Yellow
        Write-Host '$env:STAGING_GATE_KEY="..."' -ForegroundColor Yellow
        Write-Host '$env:STAGING_USER_EMAIL="..."' -ForegroundColor Yellow
        Write-Host '$env:STAGING_USER_PASSWORD="..."' -ForegroundColor Yellow
        Write-Host '$env:STAGING_ADMIN_EMAIL="..."' -ForegroundColor Yellow
        Write-Host '$env:STAGING_ADMIN_PASSWORD="..."' -ForegroundColor Yellow
        Write-Host '$env:TMONEY_WEBHOOK_SECRET="..."' -ForegroundColor Yellow
        Write-Host '$env:THUNES_WEBHOOK_SECRET="..."' -ForegroundColor Yellow
        Write-Host '$env:BOOTSTRAP_ADMIN_SECRET="..."' -ForegroundColor Yellow
        return
    }
}

$env:STAGING_BASE_URL = "https://nepxy-staging.fly.dev"
if (-not $env:BASE_URL) { $env:BASE_URL = $env:STAGING_BASE_URL }
if (-not $loadedLocal) {
    $env:STAGING_GATE_KEY = $envMap["STAGING_GATE_KEY"]
    $env:STAGING_USER_EMAIL = $envMap["STAGING_USER_EMAIL"]
    $env:STAGING_USER_PASSWORD = $envMap["STAGING_USER_PASSWORD"]
    $env:STAGING_ADMIN_EMAIL = $envMap["STAGING_ADMIN_EMAIL"]
    $env:STAGING_ADMIN_PASSWORD = $envMap["STAGING_ADMIN_PASSWORD"]
    if (-not $env:STAGING_USER_EMAIL) { $env:STAGING_USER_EMAIL = $envMap["USER_EMAIL"] }
    if (-not $env:STAGING_USER_PASSWORD) { $env:STAGING_USER_PASSWORD = $envMap["USER_PASSWORD"] }
    if (-not $env:STAGING_ADMIN_EMAIL) { $env:STAGING_ADMIN_EMAIL = $envMap["ADMIN_EMAIL"] }
    if (-not $env:STAGING_ADMIN_PASSWORD) { $env:STAGING_ADMIN_PASSWORD = $envMap["ADMIN_PASSWORD"] }
    $env:TMONEY_WEBHOOK_SECRET = $envMap["TMONEY_WEBHOOK_SECRET"]
    $env:THUNES_WEBHOOK_SECRET = $envMap["THUNES_WEBHOOK_SECRET"]
    $env:BOOTSTRAP_ADMIN_SECRET = $envMap["BOOTSTRAP_ADMIN_SECRET"]
}

$stagingUserEmail = $env:STAGING_USER_EMAIL
$stagingUserPassword = $env:STAGING_USER_PASSWORD
$stagingAdminEmail = $env:STAGING_ADMIN_EMAIL
$stagingAdminPassword = $env:STAGING_ADMIN_PASSWORD
$stagingGateKey = $env:STAGING_GATE_KEY
$bootstrapSecret = $env:BOOTSTRAP_ADMIN_SECRET
$tmoneySecret = $env:TMONEY_WEBHOOK_SECRET
$thunesSecret = $env:THUNES_WEBHOOK_SECRET

if (-not $stagingUserEmail -and $env:USER_EMAIL) {
    $stagingUserEmail = $env:USER_EMAIL
    $env:STAGING_USER_EMAIL = $stagingUserEmail
}
if (-not $stagingUserPassword -and $env:USER_PASSWORD) {
    $stagingUserPassword = $env:USER_PASSWORD
    $env:STAGING_USER_PASSWORD = $stagingUserPassword
}
if (-not $stagingAdminEmail -and $env:ADMIN_EMAIL) {
    $stagingAdminEmail = $env:ADMIN_EMAIL
    $env:STAGING_ADMIN_EMAIL = $stagingAdminEmail
}
if (-not $stagingAdminPassword -and $env:ADMIN_PASSWORD) {
    $stagingAdminPassword = $env:ADMIN_PASSWORD
    $env:STAGING_ADMIN_PASSWORD = $stagingAdminPassword
}

if ($stagingUserEmail) { $env:USER_EMAIL = $stagingUserEmail }
if ($stagingUserPassword) { $env:USER_PASSWORD = $stagingUserPassword }
if ($stagingAdminEmail) { $env:ADMIN_EMAIL = $stagingAdminEmail }
if ($stagingAdminPassword) { $env:ADMIN_PASSWORD = $stagingAdminPassword }
if ($bootstrapSecret) { $env:BOOTSTRAP_ADMIN_SECRET = $bootstrapSecret }
if ($tmoneySecret) { $env:TMONEY_WEBHOOK_SECRET = $tmoneySecret }
if ($thunesSecret) { $env:THUNES_WEBHOOK_SECRET = $thunesSecret }
if ($stagingGateKey) { $env:STAGING_GATE_KEY = $stagingGateKey }
if ($env:STAGING_BASE_URL) { $env:BASE_URL = $env:STAGING_BASE_URL }

Write-Host "Staging env loaded from Fly:"
Write-Host ("STAGING_BASE_URL=" + $env:STAGING_BASE_URL)
Write-Host ("BASE_URL=" + $env:BASE_URL)
Write-Host ("STAGING_GATE_KEY=" + (Mask-Value $env:STAGING_GATE_KEY))
Write-Host ("STAGING_USER_EMAIL=" + (Mask-Value $env:STAGING_USER_EMAIL))
Write-Host ("STAGING_USER_PASSWORD=" + (Mask-Value $env:STAGING_USER_PASSWORD))
Write-Host ("STAGING_ADMIN_EMAIL=" + (Mask-Value $env:STAGING_ADMIN_EMAIL))
Write-Host ("STAGING_ADMIN_PASSWORD=" + (Mask-Value $env:STAGING_ADMIN_PASSWORD))
Write-Host ("TMONEY_WEBHOOK_SECRET=" + (Mask-Value $env:TMONEY_WEBHOOK_SECRET))
Write-Host ("THUNES_WEBHOOK_SECRET=" + (Mask-Value $env:THUNES_WEBHOOK_SECRET))
Write-Host ("BOOTSTRAP_ADMIN_SECRET=" + (Mask-Value $env:BOOTSTRAP_ADMIN_SECRET))
