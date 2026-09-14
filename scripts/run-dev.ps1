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

    throw "Không tìm thấy cổng trống từ $PreferredPort đến $($PreferredPort + 19)."
}

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot "backend\.env"
$envExampleFile = Join-Path $projectRoot "backend\.env.example"

if (-not (Test-Path $pythonExe)) {
    throw "Không tìm thấy .venv\Scripts\python.exe. Hãy tạo môi trường ảo và cài dependencies trước."
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
    Write-Host "Đã tạo .env cho local dev." -ForegroundColor Green
}

$selectedPort = Get-FreePort -PreferredPort $Port
$baseUrl = "http://127.0.0.1:$selectedPort/"

Set-Location $projectRoot

Write-Host "Đang đồng bộ database..." -ForegroundColor Cyan
& $pythonExe manage.py setup

Write-Host "Mở đúng URL này trong trình duyệt:" -ForegroundColor Green
Write-Host "  https://127.0.0.1:$selectedPort/" -ForegroundColor Green
Write-Host "Admin:" -ForegroundColor Green
Write-Host "  https://127.0.0.1:${selectedPort}/admin/" -ForegroundColor Green
Write-Host "Đây là HTTPS (daphne + chứng chỉ self-signed)." -ForegroundColor Yellow

if (-not $NoBrowser) {
    try {
        Start-Process "https://127.0.0.1:$selectedPort/" | Out-Null
    } catch {
        Write-Host "Không thể tự động mở trình duyệt. Hãy mở URL bên trên thủ công." -ForegroundColor Yellow
    }
}

$certFile = "backend/ssl/cert.pem"
$keyFile = "backend/ssl/key.pem"
if (-not (Test-Path "$projectRoot\$certFile")) {
    & $pythonExe "$projectRoot\scripts\gen-cert.py"
}

$env:PYTHONPATH = (Join-Path $projectRoot "backend") + ";" + $env:PYTHONPATH
$daphneEndpoint = "ssl:{0}:privateKey={1}:certKey={2}" -f $selectedPort, $keyFile, $certFile
& $pythonExe -m daphne -e $daphneEndpoint config.asgi:application
exit $LASTEXITCODE
