param(
    [int]$Port = 8443,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$certFile = Join-Path $projectRoot "backend\ssl\cert.pem"
$keyFile = Join-Path $projectRoot "backend\ssl\key.pem"

$env:PYTHONPATH = (Join-Path $projectRoot "backend") + ";" + $env:PYTHONPATH
$certFile = "backend/ssl/cert.pem"
$keyFile = "backend/ssl/key.pem"
if (-not (Test-Path "$projectRoot\$certFile")) {
    & $pythonExe "$projectRoot\scripts\gen-cert.py"
}
Set-Location $projectRoot

Write-Host "Đang chạy HTTPS dev server tại: https://localhost:$Port/" -ForegroundColor Green
Write-Host "Admin: https://localhost:${Port}/admin/" -ForegroundColor Green
Write-Host ""

if (-not $NoBrowser) {
    try { Start-Process "https://localhost:$Port/" } catch {}
}

$daphneEndpoint = "ssl:{0}:privateKey={1}:certKey={2}" -f $Port, $keyFile, $certFile
& $pythonExe -m daphne -e $daphneEndpoint config.asgi:application
