# Hướng Dẫn Chi Tiết

## Yêu cầu hệ thống

- **Python** 3.12 trở lên
- **pip** (Python package manager)
- **SQL Server** 2017+ (local hoặc remote) — đã bật TCP/IP, port 1433
- **ODBC Driver 17 for SQL Server** — [tải tại đây](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

---

## Cài đặt

### 1. Tạo môi trường ảo

```powershell
python -m venv .venv
```

### 2. Kích hoạt môi trường ảo

```powershell
.\.venv\Scripts\Activate.ps1
```

Nếu bị chặn script:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Cài thư viện

```powershell
pip install -r requirements.txt
```

### 4. Cấu hình môi trường

Tạo file `backend/.env` với nội dung:

```env
DJANGO_SECRET_KEY=summarease-local-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=*

# Database — SQL Server
DB_ENGINE=sqlserver
DB_NAME=SummarEase_Django
DB_HOST=127.0.0.1
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=Admin@123
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_USE_WINDOWS_AUTH=False
```

#### Windows Auth (thay cho SQL Auth)

```env
DB_ENGINE=sqlserver
DB_NAME=SummarEase_Django
DB_HOST=127.0.0.1
DB_PORT=1433
DB_USE_WINDOWS_AUTH=True
```

#### Gemini API (tuỳ chọn)

```env
GEMINI_API_KEY=your_google_api_key
```

### 5. Tạo database SQL Server

Mở **SQL Server Management Studio** hoặc dùng `sqlcmd`:

```sql
CREATE DATABASE SummarEase_Django;
```

Hoặc chạy script:
```powershell
sqlcmd -S 127.0.0.1 -U sa -P "Admin@123" -i backend\sql\schema_sqlserver.sql
```

### 6. Migrate + tạo admin

Cách nhanh nhất:
```powershell
python manage.py setup
```

Lệnh này sẽ:
- Chạy **migrate** (tạo tất cả tables)
- **Không** tạo superuser (trừ khi thêm `--create-superuser`)

Tạo admin thủ công:
```powershell
python manage.py createsuperuser
```

---

## Chạy server

### HTTP (cổ điển)

```powershell
.\scripts\run-dev.ps1
# hoặc
python manage.py runserver
```

Mặc định: **http://127.0.0.1:8000/**

### HTTPS (khi trình duyệt ép buộc HTTPS)

```powershell
.\scripts\run-ssl.ps1              # Port 8443
.\scripts\run-ssl.ps1 -Port 8443   # Custom port
```

Mặc định: **https://localhost:8443/**

> Server HTTPS dùng **Daphne** (ASGI) + chứng chỉ self-signed + whitenoise cho static files.

---

## Endpoints API

### Web

| Endpoint | Method | Mô tả | Auth |
|----------|--------|-------|------|
| `/` | GET | Trang chủ | Không |
| `/login/` | GET, POST | Đăng nhập | Không |
| `/register/` | GET, POST | Đăng ký | Không |
| `/logout/` | POST | Đăng xuất | Có |
| `/settings/` | GET, POST | Cài đặt API key | Có |
| `/history/` | GET | Lịch sử tóm tắt | Có |
| `/history/:id/` | GET | Chi tiết tóm tắt | Có |
| `/history/:id/delete/` | POST | Xoá tóm tắt | Có |

### API

| Endpoint | Method | Mô tả | Auth |
|----------|--------|-------|------|
| `/api/summaries/create/` | POST | Tạo tóm tắt mới | Có |
| `/health/` | GET | Health check | Không |

---

## Các lệnh hữu ích

```powershell
python manage.py check                  # Kiểm tra hệ thống
python manage.py test                   # Chạy tất cả test (96 tests)
python manage.py test summaries         # Chạy test app summaries
python manage.py setup                  # Migrate + (tuỳ chọn) tạo superuser
python manage.py setup --create-superuser  # Migrate + tạo admin luôn
python manage.py createsuperuser        # Tạo superuser thủ công
python manage.py runserver              # Chạy dev server HTTP
python manage.py runserver 0.0.0.0:8001 # Custom host:port
python manage.py collectstatic          # Gom file tĩnh
python manage.py makemigrations         # Tạo migration mới
python manage.py migrate                # Áp migration
python manage.py migrate --plan         # Xem kế hoạch migrate
```

---

## Xử lý lỗi thường gặp

### Không kết nối được SQL Server

```powershell
# Kiểm tra SQL Server đã chạy chưa
Get-Service MSSQLSERVER

# Kiểm tra TCP/IP đã bật chưa
# Mở SQL Server Configuration Manager -> SQL Server Network Configuration
# -> Protocols for MSSQLSERVER -> TCP/IP -> Enabled = Yes

# Kiểm tra kết nối
sqlcmd -S 127.0.0.1 -U sa -P "Admin@123" -Q "SELECT 1"
```

### Lỗi "Login failed for user 'sa'"

```powershell
# Reset password cho sa
sqlcmd -S 127.0.0.1 -Q "ALTER LOGIN [sa] WITH PASSWORD = 'Admin@123'; ALTER LOGIN [sa] ENABLE;"
```

### Lỗi "Invalid object name 'summaries_summary'"

Tables bị thiếu sau khi reset DB. Chạy lại migrate:

```powershell
python manage.py migrate
```

### Lỗi SSL (ERR_SSL_PROTOCOL_ERROR)

Trình duyệt tự động chuyển sang HTTPS. Dùng `scripts/run-ssl.ps1` thay vì `runserver`:

```powershell
.\scripts\run-ssl.ps1
```

Hoặc gõ chính xác `http://127.0.0.1:8000/` (với http, không https).

### Cổng 8000 đã được sử dụng

```powershell
python manage.py runserver 8001
.\scripts\run-ssl.ps1 -Port 8444
```

### Thiếu thư viện

```powershell
pip install -r requirements.txt
```

### Không kích hoạt được .venv

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Gemini không hoạt động

- Kiểm tra `GEMINI_API_KEY` trong `backend/.env`
- Kiểm tra kết nối internet
- Kiểm tra API key còn hiệu lực

### Lỗi "No module named 'config'" khi chạy script

Set PYTHONPATH trước khi chạy:

```powershell
$env:PYTHONPATH = "backend"
python backend/run_https.py
```
