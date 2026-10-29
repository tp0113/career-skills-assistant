<#
.SYNOPSIS
  Builds the UI if web/dist is missing, then starts the API and UI on http://localhost:8000.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
#>
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No .venv found. Create it first (see AGENTS.md)."
    exit 1
}
$dist = Join-Path $root "web\dist\index.html"
if (-not (Test-Path $dist)) {
    Write-Host "Building the UI..."
    Push-Location (Join-Path $root "web")
    npm install --no-audit --no-fund
    npm run build
    $built = $LASTEXITCODE
    Pop-Location
    if ($built -ne 0) { Write-Host "UI build failed."; exit 1 }
}
Write-Host "Open http://localhost:8000 (Ctrl+C to stop)"
Set-Location $root
& $python -m uvicorn app.api:app --port 8000
