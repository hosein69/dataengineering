$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE="1"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
$env:PYTHONUNBUFFERED="1"
Write-Host "============================================================"
Write-Host "GSI OFFLINE DIAGNOSTIC - VISIBLE RUNNER"
Write-Host "============================================================"
Write-Host "Package/Data folder: $PSScriptRoot"
Write-Host ""
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path $python)) { $python = "python" }
& $python -u -B .\offline_validation\run_offline_diagnostic.py --data-dir "$PSScriptRoot" @args
$rc=$LASTEXITCODE
Write-Host ""
Write-Host "Feedback is under: $PSScriptRoot\offline_feedback"
Write-Host "Exit code: $rc (0=PASS, 2=HOLD/valid findings)"
Read-Host "Press Enter to close"
exit $rc
