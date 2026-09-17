# Kiến trúc SummarEase

## Phạm vi

SummarEase là ứng dụng Django 5.2 dạng MVT, gồm giao diện server-rendered và JavaScript/CSS tĩnh. Đây là dự án demo/học tập: cấu hình mặc định dùng SQLite, không cần Redis hay Gemini. TextRank chạy trong ứng dụng; Gemini là tích hợp tùy chọn, gọi dịch vụ Google khi người dùng chọn và đã có khóa.

## Thành phần

| Thành phần | Vai trò |
|---|---|
| Django `backend/config/` | Settings, URL routing, WSGI/ASGI, middleware bảo mật, request ID và logging |
| Django app `backend/summaries/` | Tài khoản, biểu mẫu, tóm tắt, lịch sử, chia sẻ, webhook, xuất tệp và API |
| NLP và trích xuất | TextRank nội bộ; Gemini tùy chọn; đọc TXT/Markdown, PDF, DOCX, EPUB và nội dung URL |
| Giao diện `frontend/` | Django templates, CSS và JavaScript thuần; không cần frontend build tool |
| SQLite / MySQL / SQL Server | SQLite mặc định cho local/test; MySQL và SQL Server là lựa chọn cấu hình |
| Celery + Redis | Tác vụ nền trong chế độ production khi cấu hình broker; không bắt buộc cho demo local |
| Docker Compose | Web, Redis, Celery worker và Celery Beat; database production được cung cấp bên ngoài |
| GitHub Actions | Ruff, mypy, bảo mật dependencies, test Python, tích hợp database, E2E và Docker build |

## Luồng tạo bản tóm tắt

```text
Trình duyệt
  │ POST (session + CSRF)
  ▼
Django view ──► SummaryRequestForm / SummaryService
  │ kiểm tra quyền, loại nguồn, kích thước và giới hạn request
  ▼
Text / URL / file
  │ URL được kiểm tra SSRF; file được kiểm tra phần mở rộng/kích thước
  ▼
Bộ trích xuất nội dung ──► TextRank nội bộ hoặc Gemini tùy chọn
  ▼
Database: Document + Summary (+ câu/tag liên quan)
  │
  ├── DEBUG/test: xử lý đồng bộ
  └── production có Redis: Celery task và trả task ID
  ▼
Giao diện hiển thị kết quả / lịch sử / chia sẻ / xuất Markdown-DOCX-PDF
```

Các file tải lên được giới hạn 10 MB. URL ngoài có kiểm tra địa chỉ đích và redirect, timeout và giới hạn response; đây là biện pháp giảm rủi ro SSRF, không thay thế egress firewall khi triển khai công khai.

## Tác vụ nền và webhook

Trong cấu hình production của Docker Compose, web, worker và Beat dùng chung database ngoài và Redis nội bộ. Tác vụ tóm tắt được đưa vào Celery. Nếu Redis chưa sẵn sàng hoặc lỗi, ứng dụng trả lỗi dịch vụ nền thay vì giả vờ đã tạo tác vụ.

Khi bản tóm tắt phát sinh sự kiện webhook, bản ghi outbox được ghi trong database cùng transaction; sau commit, ứng dụng enqueue delivery. Beat quét các delivery đang chờ mỗi phút để khôi phục tình huống enqueue thất bại hoặc worker gián đoạn. Retry có giới hạn và dùng header `X-Webhook-Delivery` ổn định để bên nhận khử trùng lặp. Mô hình giao nhận là **at-least-once**, không bảo đảm exactly-once qua HTTP. Redis/Celery/Beat chỉ cần khi bật luồng production này.

## Dữ liệu và cấu hình

- Django migrations là nguồn chuẩn để tạo/cập nhật schema.
- SQLite mặc định lưu tại `backend/sql/db.sqlite3`; có thể đổi bằng `SQLITE_DB_PATH`.
- Cấu hình MySQL/SQL Server đặt qua `DB_ENGINE` và các biến `DB_*` trong `backend/.env`.
- Docker Compose production yêu cầu MySQL hoặc SQL Server bên ngoài; SQLite không phù hợp với nhiều tiến trình web/worker trong cấu hình đó.
- `backend/.env.example` chứa cấu hình mẫu; file `backend/.env`, khóa thật, media và chứng chỉ local không được commit.
- Khóa Gemini có thể cấu hình ở cấp hệ thống hoặc người dùng. Khóa người dùng được mã hóa trong database; nội dung đưa vào Gemini được gửi tới Google.
- Không có tài khoản tạo sẵn. `python manage.py setup` chạy migrations; dùng giao diện để đăng ký hoặc `createsuperuser` cho quản trị.

## Sơ đồ thư mục rút gọn

```text
SummarEase-Django/
├── backend/
│   ├── config/                 # Settings, URLs, WSGI/ASGI, middleware
│   ├── summaries/              # Django app, API, NLP, tasks, migrations, tests
│   ├── sql/                    # SQLite mặc định và schema SQL Server tham khảo
│   ├── .env.example            # Mẫu cấu hình
│   └── conftest.py             # Cấu hình pytest
├── frontend/
│   ├── templates/              # Giao diện Django
│   ├── static/                 # CSS và JavaScript
│   └── e2e/                    # Kiểm thử Playwright
├── scripts/                    # Script chạy HTTPS/dev trên Windows
├── docs/                       # Tài liệu hướng dẫn
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── requirements.txt
└── requirements-dev.txt
```

Thư mục `media/`, chứng chỉ tự ký và SQLite local có thể được tạo khi chạy, không phải mã nguồn cần commit.

## Điểm vào quan trọng

| Điểm vào | Chức năng |
|---|---|
| `manage.py` | Lệnh quản trị Django |
| `backend/config/settings.py` | Cấu hình môi trường, database, cache/Celery và bảo mật |
| `backend/config/urls.py` | Nối giao diện, admin, API v1, schema, docs và metrics |
| `backend/summaries/urls.py` | Route trang, tóm tắt, lịch sử, webhook và health |
| `backend/summaries/services.py` | Kiểm tra đầu vào và điều phối việc tạo tóm tắt |
| `backend/summaries/readers.py` | Trích xuất tài liệu/URL và kiểm tra URL |
| `backend/summaries/nlp.py` | TextRank và tích hợp Gemini |
| `backend/summaries/tasks.py` | Tác vụ Celery và phục hồi webhook outbox |
| `frontend/static/js/app.js` | Tương tác form, kiểm tra UX và hiển thị kết quả |
| `scripts/run-dev.ps1` | Chạy Daphne HTTPS local trên Windows |
| `docker-compose.yml` | Web production mẫu, Redis, Celery worker và Beat |

## Công nghệ và kiểm tra

- Python 3.10–3.13, Django 5.2.
- HTML, CSS, JavaScript thuần; WhiteNoise phục vụ static files.
- TextRank nội bộ; Gemini API tùy chọn.
- SQLite local; MySQL/SQL Server tùy cấu hình.
- Playwright/Chromium cho E2E; pytest cho backend.
- GitHub Actions kiểm tra test nhiều phiên bản Python, MySQL, SQL Server, lint/type/security, E2E và Docker build.

Các lệnh kiểm thử và hướng dẫn chạy ứng dụng nằm trong [README](../README.md) và [hướng dẫn sử dụng](help.md). Quy trình triển khai chi tiết hơn ở [production runbook](production.md).
