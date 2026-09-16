# Hướng Dẫn Chi Tiết

## Yêu cầu hệ thống

- **Python** 3.10–3.13
- **pip** (Python package manager)
- **SQLite** — mặc định, không cần cài thêm database cho development
- **SQL Server** 2017+ và **ODBC Driver 18** — tùy chọn cho production

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

Tạo file `backend/.env` từ `backend/.env.example`. Cấu hình tối thiểu cho development:

```env
DJANGO_SECRET_KEY=summarease-local-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
# SQLite là mặc định; không cần khai báo DB_ENGINE.
```

#### SQL Server (tùy chọn)

```env
DB_ENGINE=sqlserver
DB_NAME=SummarEase_Django
DB_HOST=127.0.0.1
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=<mật-khẩu-local>
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_USE_WINDOWS_AUTH=True
```

#### Gemini API (tuỳ chọn)

```env
GEMINI_API_KEY=your_google_api_key
```

Gemini chỉ được bật khi có API key hệ thống hoặc key cá nhân đã lưu trong **Cài đặt**. Không dán key vào nội dung, URL hoặc log. Khi chưa cấu hình, lựa chọn Gemini bị vô hiệu hóa và TextRank vẫn dùng được.

### 5. Tạo database SQL Server (chỉ khi chọn SQL Server)

Mở **SQL Server Management Studio** hoặc dùng `sqlcmd`:

```sql
CREATE DATABASE SummarEase_Django;
```

Hoặc chạy script:
```powershell
sqlcmd -S 127.0.0.1 -U sa -P "<mật-khẩu-local>" -i backend\sql\schema_sqlserver.sql
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

### HTTP (Django development server)

```powershell
.\scripts\run-dev.ps1
# hoặc
python manage.py runserver
```

`run-dev.ps1` chạy HTTPS bằng Daphne tại **https://127.0.0.1:8000/**. Nếu chỉ cần HTTP, dùng lệnh `python manage.py runserver`.

### HTTPS (khuyến nghị cho giao diện local)

```powershell
.\scripts\run-dev.ps1              # Daphne, port 8000
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
| `/api/v1/summaries/create/` | POST | API versioned tạo tóm tắt | Có |
| `/api/summaries/status/<task_id>/` | GET | Kiểm tra task nền | Có |
| `/api/summaries/batch/zip/` | POST | Tóm tắt nhiều file ZIP | Có |
| `/api/summaries/batch/urls/` | POST | Tóm tắt nhiều URL | Có |
| `/history/<id>/export/<format>/` | GET | Export PDF/DOCX/Markdown | Có |
| `/history/<id>/share/` | POST | Tạo link chia sẻ 1–30 ngày | Có |
| `/share/<token>/` | GET | Xem summary được chia sẻ | Không |
| `/webhooks/` | GET/POST | Quản lý webhook | Có |
| `/metrics/` | GET | Prometheus metrics (staff/private network production) | Có* |
| `/api/schema/` | GET | OpenAPI schema | Không |
| `/api/docs/` | GET | Swagger UI | Không |
| `/health/` | GET | Health check | Không |

`Có*`: trong production cần tài khoản staff; nên giới hạn thêm bằng network policy.

---

## Các lệnh hữu ích

```powershell
python manage.py check                  # Kiểm tra hệ thống
python -m pytest backend/summaries/tests.py -q  # Chạy toàn bộ backend test
python -m pytest backend/summaries/tests.py -k Security
python manage.py setup                  # Migrate + (tuỳ chọn) tạo superuser
python manage.py setup --create-superuser  # Migrate + tạo admin luôn
python manage.py createsuperuser        # Tạo superuser thủ công
python manage.py runserver              # Chạy dev server HTTP
python manage.py runserver 0.0.0.0:8001 # Custom host:port
python manage.py collectstatic          # Gom file tĩnh
python manage.py makemigrations         # Tạo migration mới
python manage.py migrate                # Áp migration
python manage.py migrate --plan         # Xem kế hoạch migrate
python manage.py backup_db --dest backups --include-media  # Backup DB + media
```

### Kiểm thử giao diện E2E

Chạy server trong terminal riêng rồi chạy Playwright:

```powershell
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
$env:BASE_URL = "http://127.0.0.1:8000"
python -m pytest frontend/e2e/test_home.py -q
```

Bộ E2E kiểm tra chuyển nguồn, tỷ lệ, theme, trang xác thực và luồng tạo tóm tắt/chia sẻ của tài khoản mới. Playwright cần được cài theo hướng dẫn trong `requirements-dev.txt` và có Chromium tương ứng (`playwright install chromium`).

### Kiểm tra đầu vào

Trang chủ báo lỗi ngay khi chọn văn bản rỗng, URL rỗng hoặc chế độ tệp chưa chọn tệp. Đây chỉ là phản hồi UX; backend vẫn xác thực lại dữ liệu, giới hạn tệp 10 MB và chỉ nhận `.txt`, `.md`, `.markdown`, `.docx`, `.pdf`, `.epub`.

Tỷ lệ trên thanh giao diện có thể đặt từ **5% đến 80%**. Tỷ lệ mặc định của tài khoản được cấu hình riêng tại **Cài đặt**.

### Chia sẻ và xuất kết quả

Trong trang chi tiết, có thể xuất Markdown, DOCX hoặc PDF. Tạo liên kết chia sẻ sẽ tạo URL công khai cho đúng bản tóm tắt và có hạn dùng từ 1 đến 30 ngày; chỉ tạo liên kết khi thực sự muốn cho người khác truy cập.

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
sqlcmd -S 127.0.0.1 -U sa -P "<mật-khẩu-local>" -Q "SELECT 1"
```

### Lỗi "Login failed for user 'sa'"

```powershell
# Reset password cho sa
sqlcmd -S 127.0.0.1 -Q "ALTER LOGIN [sa] WITH PASSWORD = '<mật-khẩu-mới>'; ALTER LOGIN [sa] ENABLE;"
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

Chạy lệnh từ thư mục gốc dự án. Với script HTTPS, dùng:

```powershell
.\scripts\run-dev.ps1
```
