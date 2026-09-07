# ==============================================================================
# Top 1,000 GitHub Repositories Generator and Publisher (PowerShell)
# Fetches top 1,000 repositories using gh-cli, builds HTML dashboard, and pushes.
# ==============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ScriptDir

Write-Host "=== Running Top 1,000 GitHub Repositories Generator ===" -ForegroundColor Cyan

if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "Executing TypeScript generator via Node.js..." -ForegroundColor Green
    node "$ScriptDir\generate-and-push.ts"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Executing Python generator..." -ForegroundColor Green
    python "$ScriptDir\generate_and_push.py"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    Write-Host "Executing Python3 generator..." -ForegroundColor Green
    python3 "$ScriptDir\generate_and_push.py"
} else {
    Write-Error "Neither Node.js nor Python is available in PATH."
    exit 1
}

Write-Host "=== Generation and GitHub push complete ===" -ForegroundColor Cyan
