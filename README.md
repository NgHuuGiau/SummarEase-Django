# SummarEase-Django

[![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![CI](https://github.com/NgHuuGiau/SummarEase-Django/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/NgHuuGiau/SummarEase-Django/actions/workflows/ci.yml)
[![CodeQL](https://github.com/NgHuuGiau/SummarEase-Django/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/NgHuuGiau/SummarEase-Django/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Ứng dụng web Django để tóm tắt văn bản, URL và tài liệu bằng TextRank tích hợp hoặc Gemini tùy chọn. Dự án phù hợp để trình diễn và học tập; có thể chạy cục bộ mà không cần khóa API.

## Trạng thái dự án

Snapshot kiểm thử ngày **18/09/2026**:

| Hạng mục | Trạng thái |
|---|---|
| Python | 3.10–3.13 trong CI |
| Bộ tóm tắt | TextRank tích hợp; Gemini là tùy chọn |
| Đầu vào | Văn bản, URL, PDF, DOCX, EPUB, TXT và Markdown |
| Kiểm thử backend | 239 bài đạt; độ bao phủ khoảng 82% (không tính tệp kiểm thử) |
| Kiểm thử giao diện E2E | 19 bài đạt cục bộ trên Chromium |
| Cơ sở dữ liệu / hạ tầng | SQLite cho phát triển; CI kiểm tra MySQL, SQL Server và Docker build |

> Đây là kết quả kiểm thử cục bộ ngày 18/09/2026, không phải cam kết trạng thái CI hiện tại. Huy hiệu CI/CodeQL phía trên phản ánh trạng thái mới nhất trên GitHub. Trên máy Windows, một số kiểm thử tạo PDF có thể bỏ qua nếu thiếu Pango; luồng PDF được kiểm tra trên môi trường Linux của CI.

## Tính năng chính

- Tóm tắt bằng TextRank nội bộ, không cần gửi nội dung ra dịch vụ ngoài hoặc cấu hình API key.
- Có thể chọn Gemini khi đã cấu hình khóa API.
- Nhận văn bản, URL và tệp PDF, DOCX, EPUB, TXT, Markdown; tệp tải lên tối đa 10 MB, TextRank tối đa 50.000 ký tự/250 câu.
- Tài khoản, lịch sử, tìm kiếm, chia sẻ kết quả bằng liên kết có thời hạn.
- Xuất kết quả thành Markdown, DOCX hoặc PDF.
- Tóm tắt theo lô, webhook có hàng đợi sự kiện bền vững, Celery/Redis tùy chọn.
- Giao diện sáng/tối, trang kiểm tra sức khỏe, trang quản trị và tài liệu API.
- PWA cache tài nguyên tĩnh công khai; không cache trang đăng nhập, lịch sử hoặc API và không hỗ trợ gửi tóm tắt offline.

## Chạy nhanh

### Yêu cầu

- Python 3.10 trở lên (CI kiểm thử Python 3.10–3.13).
- Git.
- Không cần Docker, Redis hay khóa Gemini để chạy chế độ cơ bản.

### Cài đặt trên Windows

```powershell
git clone https://github.com/NgHuuGiau/SummarEase-Django.git
cd SummarEase-Django
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
python manage.py setup
python manage.py runserver 127.0.0.1:8000
```

Mở <http://127.0.0.1:8000/>. Nếu máy chỉ cài phiên bản Python khác trong dải được hỗ trợ, thay `3.12` bằng phiên bản tương ứng.

### Linux / macOS

```bash
git clone https://github.com/NgHuuGiau/SummarEase-Django.git
cd SummarEase-Django
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
python manage.py setup
python manage.py runserver 127.0.0.1:8000
```

Lệnh `setup` áp dụng migration cần thiết. Ứng dụng **không tạo sẵn tài khoản**; hãy đăng ký trên giao diện hoặc tự tạo tài khoản quản trị:

```bash
python manage.py createsuperuser
```

### Chạy HTTPS phát triển trên Windows

Có thể dùng script tiện ích thay cho `runserver`:

```powershell
.\scripts\run-dev.ps1
```

Script chuẩn bị môi trường `.env` nếu chưa có, áp dụng migration, tạo chứng chỉ tự ký và chạy Daphne qua HTTPS. Nó chọn một cổng khả dụng trong dải 8000–8019; hãy mở đúng URL được in ra trong terminal và chấp nhận cảnh báo chứng chỉ tự ký khi phát triển cục bộ.

## Thử nhanh luồng demo

1. Đăng ký tài khoản và đăng nhập.
2. Dán một đoạn văn bản hoặc URL, chọn TextRank rồi tạo bản tóm tắt.
3. Mở lịch sử để xem lại, chia sẻ kết quả hoặc tải xuống Markdown/DOCX.
4. Thử tải PDF/DOCX nếu muốn trình diễn xử lý tài liệu.

Luồng cơ bản dùng TextRank nên không cần cấu hình Gemini. Nếu chọn Gemini, thêm khóa vào `backend/.env`:

```dotenv
GEMINI_API_KEY=your_api_key
```

> Khi dùng Gemini, nội dung được chọn để tóm tắt sẽ được gửi tới Google theo chính sách của dịch vụ. Không đưa khóa thật vào Git; xem [hướng dẫn bảo mật](docs/SECURITY.md) và [triển khai](docs/production.md).

## Luồng xử lý

```text
Trình duyệt
    │ văn bản / URL / tệp
    ▼
Django: xác thực, kiểm tra đầu vào và trích xuất nội dung
    │
    ├── TextRank tích hợp
    └── Gemini (nếu người dùng chọn và đã cấu hình khóa)
    │
    ▼
Lưu kết quả và lịch sử ──► xem / chia sẻ / xuất tệp
    │
    └── tác vụ nền, Redis/Celery và webhook (khi được bật/cấu hình)
```

SQLite là cơ sở dữ liệu mặc định cho phát triển cục bộ. Cấu hình triển khai có thể dùng MySQL hoặc SQL Server. Docker Compose cung cấp ứng dụng, Redis, Celery worker và Celery beat; cơ sở dữ liệu được cấu hình bên ngoài, không phải một container DB mặc định trong Compose.

## Điểm vào và cấu trúc dự án

| Thành phần | Vị trí |
|---|---|
| Lệnh quản lý Django | `manage.py` |
| Cấu hình ứng dụng | `backend/config/` |
| Tính năng tóm tắt và API | `backend/summaries/` |
| Kiểm thử backend theo domain | `backend/summaries/tests.py` |
| Giao diện, CSS và JavaScript | `frontend/` |
| Kiểm thử trình duyệt Playwright | `frontend/e2e/` |
| Script chạy HTTPS phát triển trên Windows | `scripts/run-dev.ps1` |
| Cấu hình CI và CodeQL | `.github/workflows/` |
| Cấu hình pre-commit | `.pre-commit-config.yaml` |
| Docker và dịch vụ nền | `Dockerfile`, `docker-compose.yml` |
| Tài liệu dự án | `docs/` |

Các lệnh quản lý dự án bổ sung nằm trong `backend/summaries/management/commands/`. Xem sơ đồ kiến trúc chi tiết tại [docs/architecture.md](docs/architecture.md).

## Kiểm thử và kiểm tra chất lượng

Cài thêm công cụ phát triển:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Các kiểm tra cơ bản:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest backend/summaries/tests.py -q
ruff check backend manage.py
ruff format --check backend manage.py
```

### Kiểm thử giao diện E2E

Cài Chromium một lần:

```bash
python -m playwright install chromium
```

Khởi chạy ứng dụng ở terminal thứ nhất, rồi chạy trong terminal thứ hai:

```powershell
$env:BASE_URL = "http://127.0.0.1:8000"
python -m pytest frontend/e2e/test_home.py -q
```

Trên Bash, dùng `export BASE_URL="http://127.0.0.1:8000"` thay cho cú pháp PowerShell. Ma trận CI và các bước kiểm tra đầy đủ được định nghĩa tại [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Docker

Docker Compose dành cho kiểm tra/triển khai có cấu hình môi trường. Tạo `backend/.env` theo [`backend/.env.example`](backend/.env.example), cấu hình cơ sở dữ liệu và các bí mật cần thiết, sau đó chạy:

```bash
docker compose --env-file backend/.env up --build
```

Compose không tự cung cấp TLS hoặc máy chủ MySQL/SQL Server. Khi triển khai, cần cấu hình reverse proxy/TLS, cơ sở dữ liệu, Redis và proxy tin cậy phù hợp với hạ tầng thực tế. Xem [hướng dẫn production](docs/production.md) trước khi đưa lên máy chủ công khai.

## API và trang tiện ích

| Đường dẫn | Mục đích |
|---|---|
| `/api/v1/` | Các endpoint API phiên bản 1 |
| `/api/schema/` | Lược đồ OpenAPI |
| `/api/docs/`, `/api/redoc/` | Tài liệu API tương tác |
| `/health/` | Kiểm tra tình trạng ứng dụng |
| `/metrics/` | Chỉ số ứng dụng (cần cấu hình bảo vệ phù hợp khi triển khai) |
| `/admin/` | Trang quản trị Django |

## Tài liệu

- [Trợ giúp sử dụng](docs/help.md)
- [Kiến trúc hệ thống](docs/architecture.md)
- [Hướng dẫn triển khai production](docs/production.md)
- [Đóng góp và phát triển](docs/CONTRIBUTING.md)
- [Chính sách bảo mật](docs/SECURITY.md)
- [Giấy phép MIT](LICENSE)

---

Ứng dụng mẫu phục vụ học tập và trình diễn. Trước khi dùng dữ liệu nhạy cảm hoặc triển khai công khai, hãy rà soát cấu hình bảo mật, lưu trữ, sao lưu và quyền riêng tư theo môi trường thực tế.
