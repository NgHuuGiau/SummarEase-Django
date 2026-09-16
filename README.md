# 📝 SummarEase Django

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/TextRank-Summary-00ADD8" alt="TextRank">
  <img src="https://img.shields.io/badge/Gemini-AI-4285F4?logo=google-gemini&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/SQL_Server-CC2927?logo=microsoft-sql-server&logoColor=white" alt="SQL Server">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

**SummarEase Django** là ứng dụng web tóm tắt nội dung thông minh, hỗ trợ văn bản, URL và file PDF, DOCX, EPUB, TXT hoặc Markdown. Hệ thống cung cấp hai phương pháp tóm tắt: **TextRank** (chạy nội bộ) và **Gemini AI** (cần API key), cùng quản lý tài khoản, lịch sử, chia sẻ và xuất kết quả.

---

## 📋 Mục lục

- [Tính năng](#-tính-năng)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Cấu trúc dự án](#-cấu-trúc-dự-án)
- [Cài đặt nhanh](#-cài-đặt-nhanh)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
- [Chạy với Docker](#-chạy-với-docker)
- [Kiểm thử](#-kiểm-thử)
- [API Endpoints](#-api-endpoints)
- [Đóng góp](#-đóng-góp)
- [Giấy phép](#-giấy-phép)

---

## 🚀 Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| **📄 Tóm tắt văn bản** | Nhập trực tiếp nội dung cần tóm tắt |
| **🔗 Tóm tắt URL** | Trích xuất và tóm tắt nội dung trang web |
| **📁 Tải file lên** | Hỗ trợ PDF, DOCX, EPUB, TXT, Markdown (`.md`, `.markdown`); giới hạn 10 MB |
| **🧠 TextRank** | Thuật toán xếp hạng câu cổ điển, chạy nội bộ không cần API |
| **🤖 Gemini AI** | Tóm tắt thông minh bằng Google Gemini |
| **📊 Tuỳ chỉnh tỷ lệ** | Chọn mức rút gọn từ 5%–80% |
| **👤 Quản lý tài khoản** | Đăng ký, đăng nhập, phân quyền |
| **📜 Lịch sử tóm tắt** | Lưu và xem lại các bản tóm tắt đã tạo |
| **📤 Chia sẻ và xuất file** | Tạo liên kết chia sẻ có thời hạn; xuất Markdown, DOCX hoặc PDF |
| **🌓 Giao diện tối/sáng** | Theme mặc định theo hệ thống, có thể chuyển đổi |
| **✅ Kiểm tra dữ liệu đầu vào** | Báo lỗi ngay trên giao diện; backend vẫn kiểm tra lại trước khi xử lý |
| **🔒 Bảo mật** | API key được mã hoá, XSS-safe, rate limiting |

---

## 🛠 Công nghệ sử dụng

### Ngôn ngữ & Framework

| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| Python | 3.10–3.13 | Ngôn ngữ lập trình |
| Django | 5.2 | Web framework |
| HTML5 / CSS3 | — | Giao diện người dùng |
| JavaScript | Vanilla | Tương tác frontend |

### Thư viện chính

| Thư viện | Phiên bản | Mục đích |
|----------|-----------|----------|
| Python chuẩn | — | Tính điểm câu cho TextRank nội bộ |
| `PyMuPDF` | 1.28.0 | Đọc file PDF |
| `python-docx` | 1.1.0 | Đọc file DOCX |
| `ebooklib` | 0.19 | Đọc file EPUB |
| `beautifulsoup4` | 4.13.4 | Trích xuất nội dung HTML/URL |
| `requests` | 2.33.0 | Gọi API Gemini & tải URL |
| `chardet` | 5.2.0 | Phát hiện mã hoá file TXT |
| `mssql-django` | 1.7.4 | Kết nối SQL Server tùy chọn |
| `daphne` | 4.2.3 | ASGI server (HTTPS dev) |
| `whitenoise` | 6.12.0 | Phục vụ file tĩnh |
| `cryptography` | 50.0.1 | Tạo chứng chỉ SSL |
| `pytest` / `pytest-django` | — | Kiểm thử tự động |

### Cơ sở dữ liệu

- **SQLite** — mặc định cho development/test
- **SQL Server** — tùy chọn cho production (`mssql-django` + pyodbc)
- **MySQL** — tùy chọn (`PyMySQL`)

---

## 📁 Cấu trúc dự án

```
SummarEase-Django/
├── .github/workflows/       # CI/CD pipeline (GitHub Actions)
│   └── ci.yml               #   Lint, typecheck, security, test 3.10–3.13, E2E, frontend, build
├── backend/                 # Mã nguồn chính (Django)
│   ├── config/              #   Settings, URLs, WSGI/ASGI
│   │   ├── settings.py      #     Cấu hình Django (DB, whitenoise, CSP)
│   │   ├── urls.py          #     URL routing chính
│   │   ├── wsgi.py          #     WSGI entry point
│   │   ├── asgi.py          #     ASGI entry point (Daphne)
│   │   ├── csp.py           #     CSP middleware
│   │   ├── request_id.py    #     Request ID middleware
│   │   ├── logging_fmt.py   #     JSON formatter cho structured logging
│   │   └── _setup.py        #     Chung cho WSGI/ASGI
│   ├── summaries/           #   Django app chính
│   │   ├── models.py        #     Document, Summary, Tag, UserProfile, UserSetting
│   │   ├── views.py         #     View logic (health, home, login lockout, create_summary...)
│   │   ├── nlp.py           #     Xử lý NLP, TextRank (lru_cache), Gemini retry
│   │   ├── forms.py         #     Django forms
│   │   ├── admin.py         #     Django Admin config
│   │   ├── checks.py        #     System check API_ENCRYPTION_KEY prod (W001)
│   │   ├── readers.py       #     Đọc PDF/DOCX/EPUB/TXT + SSRF hop validation
│   │   ├── signing.py       #     Mã hoá API key
│   │   ├── urls.py          #     URL routing (login lockout, password reset, health, security.txt)
│   │   ├── tests.py         #     Backend tests
│   │   ├── stopwords.txt    #     Stopwords tiếng Việt
│   │   ├── management/
│   │   │   └── commands/
│   │   │       ├── setup.py     #   migrate + superuser
│   │   │       ├── backup_db.py #   backup dumpdata (+ media)
│   │   │       └── verify_backup.py # kiểm tra checksum backup
│   │   └── migrations/      #     DB migrations
│   ├── api-tests/           #   Bruno API test collection
│   ├── media/               #   File upload (gitignored)
│   ├── sql/
│   │   └── schema_sqlserver.sql # Schema SQL Server
│   ├── ssl/                 #   Chứng chỉ SSL tự ký (gitignored)
│   │   ├── cert.pem         #     Certificate
│   │   └── key.pem          #     Private key
│   ├── staticfiles/         #   Đích collectstatic (.gitkeep được theo dõi; file sinh ra bị ignore)
│   ├── .env                 #   Biến môi trường (local)
│   ├── .env.example         #   Mẫu biến môi trường
│   └── conftest.py          #   Pytest config
├── Dockerfile               # Production image (python:3.12-slim, non-root summarizease, HEALTHCHECK)
├── docker-compose.yml       # Compose: web, Redis, Celery worker và Beat
├── docs/                    # Tài liệu
│   ├── architecture.md      #   Kiến trúc hệ thống
│   ├── help.md              #   Hướng dẫn chi tiết
│   ├── CONTRIBUTING.md      #   Hướng dẫn đóng góp
│   ├── SECURITY.md          #   Chính sách bảo mật
│   └── production.md        #   Production runbook
├── frontend/                # Giao diện người dùng
│   ├── e2e/                 #   Playwright E2E tests (guest + authenticated flows)
│   ├── static/css/          #   Stylesheets (tokens-base, layout-buttons, form-area, history, pages-footer, responsive, admin.css)
│   ├── static/js/app.js     #   JavaScript
│   └── templates/           #   HTML templates
│       ├── 404.html         #     Lỗi 404
│       ├── 500.html         #     Lỗi 500
│       ├── admin/           #     Admin custom
│       └── summaries/       #     App templates (home, login, register, history_*, settings, password_reset_*)
├── scripts/                 # Scripts dev
│   ├── run-dev.bat          #   Script chạy dev HTTPS (Windows)
│   ├── run-dev.ps1          #   Script chạy dev HTTPS (Daphne, port 8000)
│   ├── run-ssl.ps1          #   Script chạy dev HTTPS (PowerShell/Daphne)
│   └── gen-cert.py          #   Tự sinh chứng chỉ SSL self-signed
├── .dockerignore
├── .gitignore
├── LICENSE
├── manage.py                # Django CLI entry point
├── pyproject.toml           # Cấu hình ruff, pytest, coverage
└── requirements.txt         # Dependencies
```

---

## ⚡ Cài đặt nhanh

### Yêu cầu

- Python 3.10–3.13
- pip
- SQLite (mặc định cho development)
- SQL Server + ODBC Driver 18 (tùy chọn cho production; đã có trong Docker image)

### Các bước

```powershell
# 1. Clone repo
git clone https://github.com/your-username/SummarEase-Django.git
cd SummarEase-Django

# 2. Tạo môi trường ảo + cài dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Nếu dùng SQL Server, tạo database và chạy schema tương ứng.
#    Development mặc định dùng SQLite, không cần bước này.

# 4. MỘT LỆNH -> migrate + chạy server
.\scripts\run-dev.bat
```

Hoặc chạy từng bước:
```powershell
python manage.py setup                    # migrate (không tạo superuser)
python manage.py setup --create-superuser # migrate + tạo admin
.\scripts\run-dev.ps1                     # daphne HTTPS trên cổng 8000
```

- Không có superuser mặc định; dùng `python manage.py createsuperuser`
- Web: **https://127.0.0.1:8000/** (tự sinh chứng chỉ SSL nếu chưa có)
- Admin: **https://127.0.0.1:8000/admin/**

### Cấu hình Gemini (tuỳ chọn)

Thêm vào `backend/.env`:
```env
GEMINI_API_KEY=your_google_api_key
```

---

## 🎯 Hướng dẫn sử dụng

1. **Đăng ký** tài khoản mới hoặc **đăng nhập**
2. Chọn nguồn dữ liệu: `Văn bản`, `File` hoặc `URL`
3. Chọn phương pháp tóm tắt: `TextRank` hoặc `Gemini` (Gemini cần API key hệ thống hoặc cá nhân)
4. Điều chỉnh tỷ lệ rút gọn (5%–80%)
5. Nhấn **Tóm tắt** để nhận kết quả
6. Sao chép kết quả, mở chi tiết, xuất Markdown/DOCX/PDF hoặc tạo liên kết chia sẻ có thời hạn
7. Xem lại các bản đã lưu trong mục **Lịch sử**

---

## 🔐 Chạy HTTPS

Mặc định `run-dev.ps1` đã chạy Daphne + HTTPS trên cổng 8000. Muốn chạy ở cổng khác:

```powershell
.\scripts\run-ssl.ps1              # Mặc định port 8443
.\scripts\run-ssl.ps1 -Port 8443   # Tùy chỉnh port
```

Server chạy tại **https://localhost:8443/** (hoặc port tùy chọn).

> Sử dụng **Daphne** ASGI server + chứng chỉ self-signed (tự sinh bằng `scripts/gen-cert.py`, lưu tại `backend/ssl/`) + whitenoise.

---

## 🧪 Kiểm thử

### Backend

```powershell
python -m pytest backend/summaries/tests.py -q
```

### Giao diện E2E

Khởi động server ở một terminal, sau đó chạy Playwright ở terminal khác:

```powershell
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
$env:BASE_URL = "http://127.0.0.1:8000"
python -m pytest frontend/e2e/test_home.py -q
```

E2E bao phủ trang khách, chuyển nguồn, tỷ lệ, theme, đăng nhập/đăng ký và luồng tài khoản đã xác thực gồm tạo tóm tắt, mở chi tiết, chia sẻ. Test upload hiện xác nhận tên tệp được chọn; xử lý định dạng và kích thước được kiểm thử ở backend. E2E tạo user riêng cho mỗi lần chạy.

CI kiểm tra backend trên Python 3.10–3.13, Ruff, mypy, pip-audit, E2E Playwright, cú pháp JavaScript, manifest frontend và build/deploy checks. Kết quả gần nhất có thể xem trong GitHub Actions; không cố định số test trong tài liệu vì suite thay đổi theo mã nguồn.

Chạy theo nhóm:

```powershell
python -m pytest backend/summaries/tests.py -k Nlp      # test NLP
python -m pytest backend/summaries/tests.py -k Summary  # luồng tóm tắt
python -m pytest backend/summaries/tests.py -k Security # bảo mật
python -m pytest backend/summaries/tests.py -k Error    # trang lỗi 404/500
```

**Phạm vi backend test:**

| Phạm vi | Nội dung |
|---------|----------|
| NLP | Tách câu, nhận diện ngôn ngữ, từ khóa, tiêu đề, highlight an toàn và trường hợp biên |
| Xác thực và phân quyền | Đăng ký/đăng nhập/đăng xuất, admin, lịch sử theo chủ sở hữu |
| Tóm tắt và cấu hình | TextRank, Gemini (mock), tỷ lệ, rate limit, lỗi và lưu lịch sử |
| Nguồn đầu vào | Văn bản, URL có kiểm tra SSRF, upload và trích xuất TXT/DOCX/PDF/EPUB |
| Bảo mật và vận hành | CSP/headers, CSRF, token chia sẻ, health, backup, lỗi 404/500 |

---

## 🐳 Chạy với Docker

```powershell
# Chuẩn bị: backend/.env có secret production, DB_ENGINE=mysql hoặc sqlserver,
# DB_HOST trỏ tới database có thể truy cập từ container và host công khai.
docker compose --env-file backend/.env up --build
# Mở http://localhost:8000/health/ để kiểm (trả {"status":"ok","database":"ok","media":"ok"})
docker compose logs -f web
docker compose down
```

Dockerfile: `python:3.12-slim`, user `summarizease` (non-root), HEALTHCHECK gọi `GET /health/`, COLLECTSTATIC lúc build.  
Compose: `restart: unless-stopped`, volume `media_data`, Redis có health check; web, Celery worker và Celery Beat dùng chung MySQL/SQL Server ngoài container. Outbox webhook lưu bền trong database, thử gửi lại nền và gắn `X-Webhook-Delivery` để phía nhận khử trùng lặp.

> Biến môi trường lấy từ `backend/.env`. Đổi `DJANGO_SECRET_KEY`, `API_ENCRYPTION_KEY` trong production. Xem `.env.example`.

### Checklist production

Xem [docs/production.md](docs/production.md) trước khi public hệ thống. Tối thiểu cần:

- Dùng database production có backup ngoài container và kiểm tra restore định kỳ.
- Đặt `DJANGO_SECRET_KEY`, `API_ENCRYPTION_KEY`, `DJANGO_ALLOWED_HOSTS` bằng secret manager.
- Chạy Redis trong private network, không expose port ra Internet.
- Thiết lập monitoring/alert cho web, database, Redis, Celery, disk và Gemini quota.
- Chạy load test và security review trước mỗi release lớn.

---

## 🌐 API Endpoints

| Endpoint | Phương thức | Mô tả |
|----------|------------|-------|
| `/` | GET | Trang chủ |
| `/login/` | GET/POST | Đăng nhập |
| `/register/` | GET/POST | Đăng ký |
| `/logout/` | POST | Đăng xuất |
| `/settings/` | GET/POST | Cài đặt (API key) |
| `/history/` | GET | Lịch sử tóm tắt |
| `/history/<id>/` | GET | Chi tiết bản tóm tắt |
| `/history/<id>/delete/` | POST | Xoá bản tóm tắt |
| `/api/summaries/create/` | POST | Tạo bản tóm tắt mới |
| `/api/v1/summaries/create/` | POST | API versioned tạo tóm tắt |
| `/api/summaries/status/<task_id>/` | GET | Kiểm tra trạng thái task |
| `/api/summaries/batch/zip/` | POST | Tóm tắt nhiều file ZIP |
| `/api/summaries/batch/urls/` | POST | Tóm tắt nhiều URL |
| `/history/<id>/export/<format>/` | GET | Export PDF/DOCX/Markdown |
| `/history/<id>/share/` | POST | Tạo link chia sẻ 1–30 ngày |
| `/share/<token>/` | GET | Xem summary được chia sẻ |
| `/webhooks/` | GET/POST | Quản lý webhook |
| `/metrics/` | GET | Prometheus metrics |
| `/api/schema/` | GET | OpenAPI schema |
| `/api/docs/` | GET | Swagger UI |
| `/admin/` | GET | Trang quản trị Django |

---

## 👥 Đóng góp

Xem [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) để biết chi tiết.

## 📄 Giấy phép

Dự án được phân phối dưới giấy phép MIT. Xem [LICENSE](LICENSE) để biết thêm chi tiết.
