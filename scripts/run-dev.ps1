param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Get-FreePort {
    param([int]$PreferredPort)

    for ($candidate = $PreferredPort; $candidate -lt ($PreferredPort + 20); $candidate++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $candidate)
            $listener.Start()
            $listener.Stop()
            return $candidate
        } catch {
            if ($listener) {
                $listener.Stop()
            }
        }
    }

    throw "Khong tim thay cong trong tu $PreferredPort den $($PreferredPort + 19)."
}

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot "backend\.env"
$envExampleFile = Join-Path $projectRoot "backend\.env.example"

if (-not (Test-Path $pythonExe)) {
    throw "Khong tim thay .venv\Scripts\python.exe. Hay tao moi truong ao va cai dependencies truoc."
}

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Copy-Item $envExampleFile $envFile
    } else {
        @"
DJANGO_SECRET_KEY=summarease-local-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
"@ | Set-Content -Path $envFile
    }
    Write-Host "Da tao .env cho local dev." -ForegroundColor Green
}

$selectedPort = Get-FreePort -PreferredPort $Port
$baseUrl = "http://127.0.0.1:$selectedPort/"

Set-Location $projectRoot

Write-Host "Dang dong bo database..." -ForegroundColor Cyan
& $pythonExe manage.py setup

Write-Host "Mo dung URL nay trong trinh duyet:" -ForegroundColor Green
Write-Host "  https://127.0.0.1:$selectedPort/" -ForegroundColor Green
Write-Host "Admin:" -ForegroundColor Green
Write-Host "  https://127.0.0.1:${selectedPort}/admin/" -ForegroundColor Green
Write-Host "Day la HTTPS (daphne + chung chi self-signed)." -ForegroundColor Yellow

if (-not $NoBrowser) {
    try {
        Start-Process "https://127.0.0.1:$selectedPort/" | Out-Null
    } catch {
        Write-Host "Khong the tu dong mo trinh duyet. Hay mo URL ben tren thu cong." -ForegroundColor Yellow
    }
}

$certFile = "backend/ssl/cert.pem"
$keyFile = "backend/ssl/key.pem"
if (-not (Test-Path "$projectRoot\$certFile")) {
    & $pythonExe "$projectRoot\scripts\gen-cert.py"
}

$env:PYTHONPATH = "$projectRoot\backend;$env:PYTHONPATH"
& $pythonExe -m daphne -e "ssl:$selectedPort`:privateKey=$keyFile`:certKey=$certFile" config.asgi:application
exit $LASTEXITCODE
