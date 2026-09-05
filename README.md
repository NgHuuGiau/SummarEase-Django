# 📝 SummarEase Django

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/TextRank-Summary-00ADD8" alt="TextRank">
  <img src="https://img.shields.io/badge/Gemini-AI-4285F4?logo=google-gemini&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/SQL_Server-CC2927?logo=microsoft-sql-server&logoColor=white" alt="SQL Server">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

**SummarEase Django** là ứng dụng web tóm tắt nội dung thông minh, hỗ trợ tóm tắt từ văn bản, URL hoặc file tải lên (PDF, DOCX, EPUB, TXT). Hệ thống cung cấp hai phương pháp tóm tắt: **TextRank** (cổ điển) và **Gemini AI** (hiện đại), kèm theo quản lý lịch sử và tài khoản người dùng.

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
| **📁 Tải file lên** | Hỗ trợ PDF, DOCX, EPUB, TXT |
| **🧠 TextRank** | Thuật toán xếp hạng câu cổ điển, không cần API |
| **🤖 Gemini AI** | Tóm tắt thông minh bằng Google Gemini |
| **📊 Tuỳ chỉnh tỷ lệ** | Chọn độ dài bản tóm tắt từ 10%–90% |
| **👤 Quản lý tài khoản** | Đăng ký, đăng nhập, phân quyền |
| **📜 Lịch sử tóm tắt** | Lưu và xem lại các bản tóm tắt đã tạo |
| **🌓 Giao diện tối/sáng** | Theme mặc định theo hệ thống, có thể chuyển đổi |
| **🔒 Bảo mật** | API key được mã hoá, XSS-safe, rate limiting |

---

## 🛠 Công nghệ sử dụng

### Ngôn ngữ & Framework

| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| Python | 3.12+ | Ngôn ngữ lập trình |
| Django | 5.2 | Web framework |
| HTML5 / CSS3 | — | Giao diện người dùng |
| JavaScript | Vanilla | Tương tác frontend |

### Thư viện chính

| Thư viện | Phiên bản | Mục đích |
|----------|-----------|----------|
| `sumy` | 0.11.0 | Tóm tắt TextRank |
| `numpy` | 2.3.0 | Tính toán ma trận cho TextRank |
| `PyMuPDF` | 1.28.0 | Đọc file PDF |
| `python-docx` | 1.1.0 | Đọc file DOCX |
| `ebooklib` | 0.19 | Đọc file EPUB |
| `beautifulsoup4` | 4.13.4 | Trích xuất nội dung HTML/URL |
| `requests` | 2.32.4 | Gọi API Gemini & tải URL |
| `chardet` | 5.2.0 | Phát hiện mã hoá file TXT |
| `mssql-django` | 1.7.4 | Kết nối SQL Server |
| `daphne` | 4.2.3 | ASGI server (HTTPS dev) |
| `whitenoise` | 6.12.0 | Phục vụ file tĩnh |
| `cryptography` | 44.0.3 | Tạo chứng chỉ SSL |
| `pytest` / `pytest-django` | — | Kiểm thử (112 tests) |

### Cơ sở dữ liệu

- **SQL Server** — mặc định (`mssql-django` + pyodbc)
- Hỗ trợ Windows Auth (`Trusted_Connection=yes`) hoặc SQL Auth (`sa` user)

---

## 📁 Cấu trúc dự án

```
SummarEase-Django/
├── .github/workflows/       # CI/CD pipeline (GitHub Actions)
│   └── django.yml           #   Chạy test + lint
├── backend/                 # Mã nguồn chính (Django)
│   ├── config/              #   Settings, URLs, WSGI/ASGI
│   │   ├── settings.py      #     Cấu hình Django (SQL Server, whitenoise, CSP)
│   │   ├── urls.py          #     URL routing chính
│   │   ├── wsgi.py          #     WSGI entry point
│   │   ├── asgi.py          #     ASGI entry point (Daphne)
│   │   ├── csp.py           #     CSP middleware
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
│   │   ├── tests.py         #     Tests (coverage 98%+)
│   │   ├── logging_fmt.py   #     JSON formatter cho structured logging (gộp trong config)
│   │   ├── stopwords.txt    #     Stopwords tiếng Việt
│   │   ├── management/
│   │   │   └── commands/
│   │   │       ├── setup.py     #   migrate + superuser
│   │   │       └── backup_db.py #   backup dumpdata (+ media)
│   │   └── migrations/      #     DB migrations
│   ├── api-tests/           #   Bruno API test collection
│   ├── media/               #   File upload (gitignored)
│   ├── sql/
│   │   └── schema_sqlserver.sql # Schema SQL Server
│   ├── ssl/                 #   Chứng chỉ SSL tự ký (gitignored)
│   │   ├── cert.pem         #     Certificate
│   │   └── key.pem          #     Private key
│   ├── staticfiles/         #   File tĩnh đã collect (auto-gen, gitignored)
│   ├── .env                 #   Biến môi trường (local)
│   ├── .env.example         #   Mẫu biến môi trường
│   └── conftest.py          #   Pytest config
├── Dockerfile               # Production image (python:3.12-slim, non-root summarizease, HEALTHCHECK)
├── docker-compose.yml       # Compose: build, migrate+setup, gunicorn, restart unless-stopped
├── docs/                    # Tài liệu
│   ├── architecture.md      #   Kiến trúc hệ thống
│   ├── help.md              #   Hướng dẫn chi tiết
│   ├── CONTRIBUTING.md      #   Hướng dẫn đóng góp
│   └── SECURITY.md          #   Chính sách bảo mật
├── frontend/                # Giao diện người dùng
│   ├── static/css/          #   Stylesheets (tokens-base, layout-buttons, form-area, history, pages-footer, responsive, admin.css)
│   ├── static/js/app.js     #   JavaScript
│   └── templates/           #   HTML templates
│       ├── 404.html         #     Lỗi 404
│       ├── 500.html         #     Lỗi 500
│       ├── admin/           #     Admin custom
│       └── summaries/       #     App templates (home, login, register, history_*, settings, password_reset_*)
├── scripts/                 # Scripts dev
│   ├── run-dev.bat          #   Script chạy dev (Windows)
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

- Python 3.12+
- pip
- SQL Server (local hoặc remote) — TCP/IP port 1433
- ODBC Driver 17 for SQL Server

### Các bước

```powershell
# 1. Clone repo
git clone https://github.com/your-username/SummarEase-Django.git
cd SummarEase-Django

# 2. Tạo môi trường ảo + cài dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Tạo database SQL Server (nếu chưa có)
sqlcmd -S 127.0.0.1 -U sa -P "Admin@123" -i backend\sql\schema_sqlserver.sql

# 4. MỘT LỆNH -> migrate + chạy server
.\scripts\run-dev.bat
```

Hoặc chạy từng bước:
```powershell
python manage.py setup                    # migrate (không tạo superuser)
python manage.py setup --create-superuser # migrate + tạo admin
.\scripts\run-dev.ps1                     # daphne HTTPS trên cổng 8000
```

- Superuser mặc định: `admin` / `admin`
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
3. Chọn phương pháp tóm tắt: `TextRank` hoặc `Gemini`
4. Điều chỉnh tỷ lệ tóm tắt (10%–90%)
5. Nhấn **Tóm tắt** để nhận kết quả
6. Xem lại lịch sử trong mục **Lịch sử**

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

Chạy toàn bộ bộ test (112 tests):

```powershell
python -m pytest backend -q
```

Chạy theo nhóm:

```powershell
python -m pytest backend/summaries/tests.py -k Nlp      # test NLP
python -m pytest backend/summaries/tests.py -k Summary  # luồng tóm tắt
python -m pytest backend/summaries/tests.py -k Security # bảo mật
python -m pytest backend/summaries/tests.py -k Error    # trang lỗi 404/500
```

**Phạm vi bộ test (112 tests / 27 nhóm):**

| Nhóm | Số test | Nội dung |
|------|--------:|----------|
| NLP — tách câu/từ | 5 | Viết tắt, tiếng Việt |
| NLP — chuẩn hóa | 2 | Khoảng trắng, trim |
| NLP — nhận diện ngôn ngữ | 4 | Việt/Anh theo dấu |
| NLP — từ khóa | 3 | Lọc, highlight `<mark>`, escape HTML |
| NLP — tiêu đề | 3 | Tự sinh tiêu đề |
| NLP — cắt ngắn | 2 | Văn bản dài/ngắn |
| NLP — trường hợp biên | 16 | Rỗng, ký tự đặc biệt, dấu `?!` |
| Model (Document/Summary/Profile/Health) | 6 | Tạo bản ghi, timestamp, role |
| Trang auth | 4 | Home, login, register, static CSS |
| Luồng auth | 2 | Đăng ký, đăng nhập/đăng xuất |
| Luồng tóm tắt | 6 | TextRank, lỗi, rate limit, phân quyền |
| Cài đặt | 5 | Tỉ lệ, API key mã hoá |
| Form validation | 5 | Ratio, API key, thiếu field |
| Admin | 5 | Trang quản trị, phân quyền |
| Phân trang lịch sử | 3 | Page 1/2, page lỗi |
| Phân quyền | 4 | Xoá bản ghi của mình/người khác |
| Xoá cascade | 2 | Document → Summary |
| Trích URL | 6 | Scheme lạ, timeout, bỏ script |
| Upload file | 4 | Quá lớn, định dạng, thiếu file |
| Trích file | 4 | TXT/DOCX/PDF/EPUB |
| Gemini | 5 | Thiếu key, HTTP lỗi, JSON sai (mock) |
| **Trang lỗi 404/500** | 2 | Template custom render đúng |
| **Bảo mật headers** | 5 | CSP, clickjacking, nosniff, referrer, CSRF |
| **Biên nội dung** | 3 | Text 1 ký tự, text trắng, text rất dài |
| Tóm tắt từ URL | 2 | Xem URL trên view, thiếu source_url |
| Mã hoá token | 3 | Roundtrip, rỗng, token không hợp lệ |
| Superuser → admin | 1 | Hồ sơ admin + tỉ lệ mặc định khi đăng nhập |

---

## 🐳 Chạy với Docker

```powershell
# Chuẩn bị: backend/.env đã có SECRET_KEY, ALLOWED_HOSTS, DB_ENGINE (sqlite mặc định)
docker compose up --build
# Mở http://localhost:8000/health/ để kiểm (trả {"status":"ok","database":"ok","media":"ok"})
docker compose logs -f web
docker compose down
```

Dockerfile: `python:3.12-slim`, user `summarizease` (non-root), HEALTHCHECK gọi `GET /health/`, COLLECTSTATIC lúc build.  
Compose: `restart: unless-stopped`, volume `media_data` + `sqlite_data`, lệnh `migrate && setup && gunicorn --bind 0.0.0.0:8000 --workers 3`.

> Biến môi trường lấy từ `backend/.env`. Đổi `DJANGO_SECRET_KEY`, `API_ENCRYPTION_KEY` trong production. Xem `.env.example`.

---

## 🌐 API Endpoints

| Endpoint | Phương thức | Mô tả |
|----------|------------|-------|
| `/` | GET | Trang chủ |
| `/login/` | GET/POST | Đăng nhập |
| `/register/` | GET/POST | Đăng ký |
| `/logout/` | GET | Đăng xuất |
| `/settings/` | GET/POST | Cài đặt (API key) |
| `/history/` | GET | Lịch sử tóm tắt |
| `/history/<id>/` | GET | Chi tiết bản tóm tắt |
| `/history/<id>/delete/` | POST | Xoá bản tóm tắt |
| `/api/summaries/create/` | POST | Tạo bản tóm tắt mới |
| `/admin/` | GET | Trang quản trị Django |

---

## 👥 Đóng góp

Xem [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) để biết chi tiết.

## 📄 Giấy phép

Dự án được phân phối dưới giấy phép MIT. Xem [LICENSE](LICENSE) để biết thêm chi tiết.
