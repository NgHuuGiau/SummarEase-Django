# Kiến Trúc Hệ Thống

## Tổng quan

SummarEase Django là ứng dụng web Django 5.2 với kiến trúc MVT (Model-View-Template) truyền thống, kết hợp xử lý NLP ở backend và giao diện người dùng ở frontend. Hệ thống chạy trên SQL Server, hỗ trợ HTTPS dev với Daphne + whitenoise.

## Sơ đồ thư mục

```
SummarEase-Django/
├── backend/                     # Django project
│   ├── config/                  # Settings, URLs, WSGI, ASGI
│   │   ├── settings.py          #   Cấu hình Django (SQL Server, whitenoise, CSP)
│   │   ├── urls.py              #   URL routing chính
│   │   ├── wsgi.py              #   WSGI entry point
│   │   ├── asgi.py              #   ASGI entry point (dùng cho Daphne)
│   │   ├── csp.py               #   CSP middleware
│   │   └── _setup.py            #   Chung cho WSGI/ASGI
│   ├── summaries/               # Django app chính
│   │   ├── models.py            #   Document, Summary, Tag, UserProfile, UserSetting
│   │   ├── views.py             #   View logic
│   │   ├── nlp.py               #   Xử lý NLP, TextRank, Gemini
│   │   ├── forms.py             #   Django forms
│   │   ├── admin.py             #   Django Admin config
│   │   ├── tests.py             #   112 tests
│   │   ├── stopwords.txt        #   Stopwords tiếng Việt
│   │   ├── management/
│   │   │   └── commands/
│   │   │       └── setup.py     #   Management command: migrate + create-superuser
│   │   └── migrations/          #   DB migrations
│   ├── api-tests/               #   Bruno API test collection
│   ├── media/                   #   File upload (gitignored)
│   ├── sql/                     #   Database schemas
│   │   └── schema_sqlserver.sql #     Schema SQL Server
│   ├── ssl/                     #   Chứng chỉ SSL tự ký (gitignored)
│   │   ├── cert.pem             #     Certificate
│   │   └── key.pem              #     Private key
│   ├── staticfiles/             #   File tĩnh đã collect (auto-gen, gitignored)
│   ├── .env                     #   Biến môi trường (local)
│   ├── .env.example             #   Mẫu biến môi trường
│   └── conftest.py              #   Pytest config
├── frontend/                    # Giao diện người dùng
│   ├── static/                  # File tĩnh
│   │   ├── css/tokens-base.css      #   Design tokens + reset
│   │   ├── css/layout-buttons.css   #   Header/nav + buttons/badges
│   │   ├── css/form-area.css        #   Hero + workspace + result panel
│   │   ├── css/history.css          #   History shelf & cards
│   │   ├── css/pages-footer.css     #   Detail + auth/settings + footer
│   │   ├── css/responsive.css       #   Breakpoints
│   │   ├── css/admin.css            #   Admin styles
│   │   └── js/app.js                #   JavaScript (guard is-disabled cho Gemini)
│   └── templates/               # Django templates
│       ├── 404.html             #   Lỗi 404
│       ├── 500.html             #   Lỗi 500
│       ├── admin/base_site.html #   Tuỳ chỉnh admin
│       └── summaries/           #   App templates
│           ├── base.html        #     Template gốc (load 6 CSS theo thứ tự)
│           ├── home.html        #     Trang chủ (gemini_available toggle)
│           ├── login.html       #     Đăng nhập ("Quên mật khẩu?" link)
│           ├── register.html    #     Đăng ký
│           ├── settings.html    #     Cài đặt
│           ├── history_list.html#     Lịch sử
│           ├── history_detail.html#   Chi tiết
│           ├── password_reset*.html # Password reset (4 templates)
│           └── password_reset_email.txt # Email khôi phục
├── scripts/                     # Scripts dev
│   ├── run-dev.bat              #   Script dev HTTP (Windows)
│   ├── run-dev.ps1              #   Script dev HTTP (PowerShell)
│   └── run-ssl.ps1              #   Script dev HTTPS (PowerShell/Daphne)
├── docs/                        # Tài liệu
├── manage.py                    # Django CLI
├── requirements.txt             # Dependencies
└── pyproject.toml               # Cấu hình ruff, pytest, coverage
```

## Luồng xử lý chính

### 1. Tóm tắt nội dung

```
User -> POST /api/summaries/create/
         -> views.py: create_summary()
              -> Nếu source_type = text: dùng text trực tiếp
              -> Nếu source_type = url: requests.get() + BeautifulSoup
              -> Nếu source_type = file: đọc file (PDF/DOCX/EPUB/TXT)
         -> nlp.py: summarize_text(text, method, ratio)
              -> TextRank: sumy TextRankSummarizer
              -> Gemini: requests POST lên Gemini API
         -> Lưu Document + Summary vào database
         -> Trả kết quả về frontend
```

### 2. Xác thực

```
Django Authentication (session-based)
  -> Login: authenticate() -> login()
  -> Logout: logout()
  -> Decorator: @login_required cho các view yêu cầu đăng nhập
```

### 3. Gemini API

```
nlp.py -> requests.post(
    url = "https://generativelanguage.googleapis.com/v1beta/models/..."
    headers = { "X-Goog-Api-Key": api_key }
    json = { contents: [...] }
)
```

## Công nghệ chính

| Thành phần | Giải pháp |
|-----------|-----------|
| Web framework | Django 5.2 |
| NLP (offline) | sumy (TextRank) |
| NLP (online) | Google Gemini API |
| Database | SQL Server (mssql-django + pyodbc) |
| ASGI server | Daphne (HTTPS dev) |
| Static files | whitenoise |
| Frontend | HTML + CSS + Vanilla JS |
| CI/CD | GitHub Actions |
| Management | python manage.py setup |

## Database

### SQL Server

- **Engine**: `mssql` (django-mssql-backend)
- **Auth**: Windows Auth (`Trusted_Connection=yes`) hoặc SQL Auth (`sa` user)
- **Driver**: ODBC Driver 17 for SQL Server
- **Schema**: `backend/sql/schema_sqlserver.sql`
- **Cấu hình**: biến môi trường `DB_ENGINE`, `DB_NAME`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_DRIVER`

## HTTPS Dev

Hệ thống sử dụng **Daphne** làm ASGI server cho HTTPS development:
- Script: `scripts/run-ssl.ps1`
- Port mặc định: 8443
- Chứng chỉ self-signed (`backend/ssl/cert.pem`, `backend/ssl/key.pem`) tạo bằng `cryptography`
- Static files được phục vụ qua **whitenoise** middleware

## Bảo mật

- **API key**: Lưu trong `.env`, gửi qua header (không lộ trong URL)
- **XSS**: `html.escape()` nội dung trước khi highlight keyword
- **CSRF**: Django CSRF middleware
- **CSP**: Content-Security-Policy headers qua middleware custom
- **File upload**: Validate loại file, xoá file khi xoá Document
- **Rate limiting**: 5s giữa các request tóm tắt

## Management Commands

| Lệnh | Mô tả |
|------|-------|
| `python manage.py setup` | Migrate DB + tạo superuser (nếu `--create-superuser`) |
| `python manage.py migrate` | Áp migration |
| `python manage.py collectstatic` | Gom file tĩnh |
| `python manage.py test` | Chạy tất cả tests (112 tests) |
