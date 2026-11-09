# Windows setup: creates .venv, installs dependencies, pulls the local LLM with Ollama, runs a smoke check.
# Safe to run more than once.
# Usage: powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"

function Invoke-Step([string]$Label, [scriptblock]$Command) {
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $Label (exit code $LASTEXITCODE)" }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Step "Create virtual environment (Python 3.12)" { py -3.12 -m venv .venv }
    } else {
        Invoke-Step "Create virtual environment (python on PATH)" { python -m venv .venv }
    }
}
$py = ".\.venv\Scripts\python.exe"
Invoke-Step "Check Python version" { & $py -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 is required, found ' + sys.version" }
Invoke-Step "Upgrade pip" { & $py -m pip install --quiet --upgrade pip }
Invoke-Step "Install dependencies" { & $py -m pip install --quiet -r requirements.txt -r requirements-dev.txt }
Invoke-Step "Install this package" { & $py -m pip install --quiet --no-deps -e . }

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    # A fresh install is not on this session's PATH yet: look in the default install folder.
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $candidate) { $ollama = Get-Item $candidate }
}
if ($ollama) {
    $model = & $py -c "from brand_voice.config import load_config; print(load_config()['ollama']['model'])"
    Invoke-Step "Pull local LLM $model with Ollama (first run only, ~3.3 GB)" { & $ollama.Source pull $model }
} else {
    Write-Host "`n[!] Ollama not found. The app will open in demo mode with pre-generated texts." -ForegroundColor Yellow
    Write-Host "    To generate live: install it from https://ollama.com/download (or: winget install --id Ollama.Ollama -e)," -ForegroundColor Yellow
    Write-Host "    then run this setup again.`n" -ForegroundColor Yellow
}
Invoke-Step "Smoke check" { & $py -m brand_voice.smoke }
Write-Host "`nSetup complete. Start the app with: powershell -ExecutionPolicy Bypass -File .\run.ps1"
