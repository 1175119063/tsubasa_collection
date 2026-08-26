$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot '.conda\envs\tsubasa\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Get-ChildItem -LiteralPath (Join-Path $projectRoot '.conda\envs') `
        -Filter 'python.exe' -File -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $pythonPath) {
    throw 'Project Conda environment was not found. See ENVIRONMENT.md.'
}

Set-Location -LiteralPath $projectRoot
Write-Host 'Tsubasa demo: http://127.0.0.1:8000' -ForegroundColor Green
Write-Host 'Press Ctrl+C to stop the server.' -ForegroundColor DarkGray

& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
