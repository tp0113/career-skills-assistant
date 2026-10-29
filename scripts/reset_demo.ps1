<#
.SYNOPSIS
  Clears demo enrollments (var/enrollments.json) so the demo starts clean. Seed data is never touched.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/reset_demo.ps1
#>
$root = Split-Path -Parent $PSScriptRoot
$file = Join-Path $root "var\enrollments.json"
if (Test-Path $file) {
    Remove-Item $file
    Write-Host "Deleted $file"
} else {
    Write-Host "Nothing to delete: $file does not exist"
}
