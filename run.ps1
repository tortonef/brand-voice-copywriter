# Launch the app. Usage: powershell -ExecutionPolicy Bypass -File .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Run setup.ps1 first." }
& .\.venv\Scripts\python.exe -m streamlit run app.py
