$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot '.conda\envs\yuhen\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project Conda environment was not found: $pythonPath. See ENVIRONMENT.md."
}

Set-Location -LiteralPath $projectRoot
Write-Host 'Yuhen demo: http://127.0.0.1:8000' -ForegroundColor Green
Write-Host 'Press Ctrl+C to stop the server.' -ForegroundColor DarkGray

& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
