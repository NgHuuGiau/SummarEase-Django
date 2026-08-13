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
Write-Host "  $baseUrl" -ForegroundColor Green
Write-Host "Admin:" -ForegroundColor Green
Write-Host "  ${baseUrl}admin/" -ForegroundColor Green
Write-Host "Chi dung http://, khong dung https:// trong local runner nay." -ForegroundColor Yellow

if (-not $NoBrowser) {
    try {
        Start-Process $baseUrl | Out-Null
    } catch {
        Write-Host "Khong the tu dong mo trinh duyet. Hay mo URL ben tren thu cong." -ForegroundColor Yellow
    }
}

& $pythonExe manage.py runserver "127.0.0.1:$selectedPort"
exit $LASTEXITCODE
