# PowerShell script to run the spectre pipeline (Pass 1–4.3)
# Fails on first error, prints summary if all succeed

# 1. Assert running from repo root (where scripts/ exists)
if (-not (Test-Path -Path "scripts" -PathType Container)) {
    Write-Error "ERROR: Must run from repo root (where scripts/ exists)."; exit 1
}

# 2. Assert venv is active
if (-not $env:VIRTUAL_ENV) {
    Write-Error "ERROR: venv not active. Run: & .\\.venv\\Scripts\\Activate.ps1"; exit 1
}

$pythonPrefix = python -c "import sys; print(sys.prefix)" 2>&1
if ($LASTEXITCODE -ne 0 -or -not $pythonPrefix -or $pythonPrefix.Trim() -ne $env:VIRTUAL_ENV) {
    Write-Error "ERROR: venv not active. Run: & .\\.venv\\Scripts\\Activate.ps1"; exit 1
}

# 3. Run pipeline steps, stop on error
Write-Host "[1/4] Validating examples..."
python .\scripts\validate_examples.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/4] Building facts_pack.json..."
$env:PYTHONPATH = "src"
python .\scripts\build_facts_pack.py --symbols BTCUSDT,ETHUSDT --lookback-days 365 --out artifacts\facts_pack.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/4] Building decision_packet.json..."
python .\scripts\build_decision_packet.py --in artifacts\facts_pack.json --out artifacts\decision_packet.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/4] Building execution_plan.json..."
python .\scripts\build_execution_plan.py --facts artifacts\facts_pack.json --decision artifacts\decision_packet.json --out artifacts\execution_plan.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 4. Print summary
Write-Host "`nPIPELINE OK`n" -ForegroundColor Green
Write-Host "Artifacts in artifacts/:"
Get-ChildItem -File -Path artifacts | Select-Object Name,Length,LastWriteTime | Format-Table

# Print schema_version from execution_plan.json
try {
    $plan = Get-Content artifacts\execution_plan.json | ConvertFrom-Json
    if ($plan.schema_version) {
        Write-Host "`nschema_version: $($plan.schema_version)" -ForegroundColor Cyan
    } else {
        Write-Host "`nschema_version: (not found)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Could not parse schema_version from execution_plan.json" -ForegroundColor Red
}
