# scripts/env.example.ps1 (commit this; safe template)
$pgpass = Join-Path $env:APPDATA "postgresql\pgpass.conf"
$env:PGPASSFILE = $pgpass

$env:PGHOST = "127.0.0.1"
$env:PGPORT = "5432"
$env:PGUSER = "postgres"
$env:PGDATABASE = "nexapay_core"

# Put psql in PATH if needed
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
  $psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
  if (Test-Path $psqlPath) {
    $env:PATH = (Split-Path $psqlPath) + ";" + $env:PATH
  }
}
