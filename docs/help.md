# Hướng dẫn sử dụng và chạy cục bộ

Tài liệu này hướng dẫn chạy SummarEase từ thư mục gốc repository. Mặc định, ứng dụng dùng SQLite và TextRank nên không cần máy chủ database, Redis, Docker hay khóa Gemini.

## Yêu cầu

- Python 3.10–3.13 (các phiên bản này được kiểm tra trong CI).
- Git và pip.
- Chromium chỉ cần khi chạy kiểm thử giao diện Playwright.
- Pango trên Windows nếu muốn xuất PDF bằng WeasyPrint; có thể dùng Docker/WSL hoặc cài theo [hướng dẫn WeasyPrint](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html#windows).

MySQL và SQL Server là các lựa chọn cấu hình bổ sung. Không cần cài một trong hai để chạy demo cục bộ.

## Cài đặt

### Windows (PowerShell)

Chạy từ thư mục gốc dự án:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py setup
python manage.py runserver 127.0.0.1:8000
```

Thay `3.12` bằng phiên bản Python đã cài nếu cần. Nếu PowerShell chặn kích hoạt môi trường ảo, chỉ cho phép trong cửa sổ hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py setup
python manage.py runserver 127.0.0.1:8000
```

Mở <http://127.0.0.1:8000/>. Lệnh `setup` áp dụng migration và không tạo tài khoản quản trị. Người dùng có thể đăng ký trực tiếp; để vào Django Admin, chạy:

```bash
python manage.py createsuperuser
```

Không có tài khoản mặc định.

## Cấu hình tùy chọn

Cấu hình được đọc từ biến môi trường và `backend/.env`. Chạy `scripts/run-dev.ps1` trên Windows sẽ tự tạo `backend/.env` từ `backend/.env.example` nếu tệp chưa có. Khi chạy `runserver`, nếu chưa tạo `.env`, ứng dụng vẫn khởi động bằng cấu hình phát triển mặc định.

### Gemini

TextRank là lựa chọn mặc định và không cần API key. Để bật Gemini, cấu hình `GEMINI_API_KEY` trong `backend/.env`, hoặc lưu khóa cá nhân tại trang **Cài đặt** sau khi đăng nhập. Khi dùng Gemini, nội dung được chọn để tóm tắt sẽ được gửi tới Google; không dùng dữ liệu nhạy cảm trong demo và không commit khóa thật.

### MySQL hoặc SQL Server

Cơ sở dữ liệu mặc định là SQLite tại `backend/sql/db.sqlite3`. Nếu chọn database khác, đặt `DB_ENGINE` cùng thông tin kết nối trong `backend/.env`. Các migration Django tạo/cập nhật bảng; không cần chạy thủ công `backend/sql/schema_sqlserver.sql` cho cài đặt mới.

MySQL dùng `DB_ENGINE=mysql`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`. SQL Server dùng `DB_ENGINE=sqlserver`, các biến kết nối tương ứng và ODBC Driver 18. Có thể dùng Windows Authentication bằng `DB_USE_WINDOWS_AUTH=True` trong môi trường hỗ trợ.

## Chạy HTTPS trên Windows

Để chạy Daphne với chứng chỉ tự ký trong môi trường phát triển:

```powershell
.\scripts\run-dev.ps1
```

Script yêu cầu môi trường ảo ở `.venv`, chạy `manage.py setup`, tự chọn cổng trống từ cổng bắt đầu (mặc định 8000) đến 19 cổng tiếp theo, rồi in URL HTTPS chính xác. Trình duyệt có thể cảnh báo chứng chỉ tự ký; chỉ chấp nhận khi đang truy cập máy local.

Script thay thế `scripts/run-ssl.ps1` dùng cổng 8443 mặc định và nhận tham số `-Port`, ví dụ `.scripts\run-ssl.ps1 -Port 8444`. Hai script này chỉ phục vụ phát triển, không thay thế cấu hình TLS production.

## Luồng demo

1. Đăng ký tài khoản trên trang chủ.
2. Nhập văn bản, URL hoặc chọn tệp rồi giữ phương pháp TextRank để chạy không cần API key.
3. Mở **Lịch sử** để xem lại kết quả.
4. Từ trang chi tiết, thử chia sẻ liên kết (1–30 ngày) hoặc xuất Markdown/DOCX/PDF.
5. Mở **Cài đặt** để đổi tỷ lệ mặc định hoặc cấu hình Gemini cá nhân.

Định dạng tải lên gồm TXT, Markdown, DOCX, PDF và EPUB; giới hạn thông thường là 10 MB mỗi tệp. Tóm tắt URL kiểm tra đích mạng và có giới hạn kích thước phản hồi. Chỉ nhập URL công khai mà bạn được phép truy cập.
TextRank giới hạn 50.000 ký tự và tối đa 250 câu để tránh tác vụ quá nặng.
PWA chỉ lưu tài nguyên tĩnh để tải nhanh; cần kết nối mạng để đăng nhập và sử dụng các chức năng.

## Endpoint chính

Các route trong bảng dưới đây là đường dẫn tương đối với host ứng dụng:

| Đường dẫn | Phương thức | Mục đích / quyền truy cập |
|---|---|---|
| `/`, `/login/`, `/register/` | GET/POST tùy trang | Trang chủ và xác thực |
| `/settings/`, `/history/`, `/history/<id>/` | GET/POST tùy trang | Cài đặt và lịch sử; cần đăng nhập |
| `/api/summaries/create/` | POST | Tạo tóm tắt; cần đăng nhập và CSRF |
| `/api/v1/summaries/create/` | POST | Route tạo tóm tắt phiên bản 1 |
| `/api/summaries/status/<task_id>/` | GET | Kiểm tra tác vụ; chỉ chủ sở hữu tác vụ |
| `/api/v1/summaries/status/<task_id>/` | GET | Route trạng thái phiên bản 1 |
| `/api/summaries/batch/zip/`, `/api/summaries/batch/urls/` | POST | Xử lý tuần tự theo lô; cần đăng nhập và CSRF; phù hợp demo nhỏ |
| `/history/<id>/export/<format>/` | GET | Xuất Markdown, DOCX hoặc PDF; cần quyền với bản tóm tắt |
| `/history/<id>/share/` | POST | Tạo liên kết chia sẻ; cần đăng nhập và CSRF |
| `/share/<token>/` | GET | Xem bản tóm tắt được chia sẻ bằng token |
| `/webhooks/` | GET/POST | Xem/tạo webhook; cần đăng nhập |
| `/webhooks/<id>/delete/`, `/webhooks/<id>/test/` | POST | Xóa hoặc gửi thử webhook; cần đăng nhập và CSRF |
| `/health/` | GET | Kiểm tra database và thư mục media |
| `/api/schema/`, `/api/docs/`, `/api/redoc/` | GET | OpenAPI, Swagger UI và ReDoc |
| `/metrics/` | GET | Prometheus; production chỉ dành cho staff |
| `/admin/` | GET/POST | Django Admin; cần tài khoản staff |

Các endpoint POST dùng session trình duyệt cần CSRF token. Không tắt CSRF để chạy thử.

## Kiểm thử

Cài dependencies phát triển và trình duyệt:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
```

Chạy backend tests:

```bash
python -m pytest backend/summaries/tests.py -q
```

E2E cần ứng dụng đang chạy ở terminal khác:

```powershell
$env:BASE_URL = "http://127.0.0.1:8000"
python -m pytest frontend/e2e/test_home.py -q
```

Trong Bash, đặt URL bằng `export BASE_URL="http://127.0.0.1:8000"`. CI định nghĩa ma trận và các bước kiểm tra đầy đủ tại [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Xử lý lỗi thường gặp

### Cổng HTTP 8000 đang bận

Chạy Django tại cổng khác, ví dụ `python manage.py runserver 127.0.0.1:8001`. Script `run-dev.ps1` tự tìm cổng trống trong dải 20 cổng bắt đầu từ tham số `-Port`.

### Lỗi chứng chỉ hoặc ERR_SSL_PROTOCOL_ERROR

`runserver` phục vụ HTTP; dùng URL `http://127.0.0.1:8000/`. Script `run-dev.ps1` và `run-ssl.ps1` phục vụ HTTPS bằng chứng chỉ tự ký; dùng đúng URL HTTPS mà script in ra.

### Không kết nối được SQL Server

Kiểm tra dịch vụ SQL Server, bật TCP/IP, xác nhận ODBC Driver 18 và thông tin trong `backend/.env`. Nếu dùng SQL Authentication, kiểm tra `DB_USER`/`DB_PASSWORD`; nếu dùng Windows Authentication, đặt `DB_USE_WINDOWS_AUTH=True`. Chạy `python manage.py migrate` sau khi kết nối được.

### Gemini bị vô hiệu hóa hoặc báo thiếu API key

Kiểm tra `GEMINI_API_KEY` trong `backend/.env` hoặc khóa cá nhân trong **Cài đặt**. TextRank vẫn hoạt động không cần khóa.

### Không gửi được email đặt lại mật khẩu

Mặc định email phát triển được ghi ra console. Để gửi thật, cấu hình SMTP trong `backend/.env`; không đưa mật khẩu email vào repository.

### Không xuất được PDF trên Windows

WeasyPrint cần Pango và các thư viện hệ điều hành. Cài theo [hướng dẫn Windows của WeasyPrint](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html#windows), hoặc thử trên Linux/WSL/Docker.

Cách đã kiểm chứng (không cần quyền admin): tải `gtk3-runtime-*-ts-win64.exe` từ [GTK-for-Windows-Runtime-Environment-Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases), cài silent vào thư mục người dùng rồi trỏ WeasyPrint tới đó:

```powershell
.\gtk3-runtime-*-ts-win64.exe /S /D="$env:LOCALAPPDATA\SummarEase\gtk3-ts"
[Environment]::SetEnvironmentVariable("WEASYPRINT_DLL_DIRECTORIES", "$env:LOCALAPPDATA\SummarEase\gtk3-ts\bin", "User")
```

Mở terminal mới và kiểm tra: `python -c "import weasyprint; print('OK')"`.
