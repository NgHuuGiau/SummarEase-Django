# Ghi chú triển khai

SummarEase hiện chủ yếu phục vụ demo/học tập. Có thể dùng SQLite và `runserver` cho local; nội dung dưới đây chỉ cần khi chạy Docker hoặc đưa ứng dụng ra mạng công khai. Đây không phải kiến trúc HA hay runbook được kiểm chứng trên hạ tầng cụ thể.

## 1. Docker Compose

Compose hiện chạy bốn dịch vụ: web, Redis, Celery worker và Celery Beat. Database **không** được tạo trong Compose; phải cung cấp MySQL hoặc SQL Server có thể truy cập từ container. SQLite phù hợp cho phát triển/test đơn tiến trình, không dùng với cấu hình đa tiến trình này.

Tạo `backend/.env` từ `backend/.env.example` và đặt tối thiểu các giá trị production:

```dotenv
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<chuỗi-ngẫu-nhiên-dài>
API_ENCRYPTION_KEY=<khóa-Fernet-riêng>
DJANGO_ALLOWED_HOSTS=app.example.com
DB_ENGINE=mysql
DB_NAME=summarease_django
DB_HOST=<hostname-database>
DB_PORT=3306
DB_USER=<tài-khoản>
DB_PASSWORD=<mật-khẩu>
REDIS_PASSWORD=<mật-khẩu-url-safe>
```

Nếu dùng SQL Server, đặt `DB_ENGINE=sqlserver`, `DB_PORT=1433` và `DB_DRIVER=ODBC Driver 18 for SQL Server` cùng thông tin xác thực tương ứng. Mặc định ứng dụng xác thực chứng chỉ máy chủ (`TrustServerCertificate=no`); chỉ đặt `DB_TRUST_SERVER_CERTIFICATE=true` cho môi trường tin cậy dùng chứng chỉ tự ký. Compose yêu cầu `DB_ENGINE`, `DJANGO_ALLOWED_HOSTS` và `REDIS_PASSWORD`. Tạo secret ngẫu nhiên, không dùng các giá trị ví dụ:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Dùng khóa Fernet hợp lệ riêng cho `API_ENCRYPTION_KEY` (tạo bằng `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`); không đổi khóa sau khi đã lưu Gemini key được mã hóa nếu chưa có kế hoạch mã hóa lại dữ liệu. Lưu secrets ngoài Git và giới hạn người được truy cập.

Khởi động:

```bash
docker compose --env-file backend/.env up --build
```

Ứng dụng được publish ở cổng 8000. Compose không cấu hình TLS và cũng không tự dựng MySQL/SQL Server. Trước khi public, đặt reverse proxy có TLS hợp lệ, giới hạn firewall để chỉ proxy tin cậy vào được cổng ứng dụng, cấu hình `TRUSTED_PROXY_IPS` theo địa chỉ proxy và giữ Redis/database trong mạng riêng. Không coi việc publish cổng 8000 mặc định là cấu hình an toàn cho Internet.

## 2. Health check và tác vụ nền

- `/health/` kiểm tra truy vấn database và khả năng ghi/xóa tệp thử trong media; HTTP 503 báo trạng thái degraded. Endpoint này không kiểm tra Gemini, Redis hay Celery.
- `/metrics/` chỉ cho staff đọc trong production. Giới hạn truy cập mạng monitoring; bộ metrics trong ứng dụng không thay cho APM hoặc giám sát hạ tầng.
- Service Worker chỉ cache tài nguyên tĩnh công khai; trang đăng nhập, lịch sử và API không được lưu offline. Đây không phải chế độ offline đầy đủ.
- Webhook outbox được lưu trong database và Celery Beat quét delivery đang chờ mỗi phút. Retry có giới hạn; giao nhận là at-least-once. Bên nhận nên khử trùng lặp theo `X-Webhook-Delivery`.
- Compose tự chạy migration khi khởi động web. Hãy backup trước khi nâng cấp schema và giữ image/version trước đó để có phương án rollback.
- Cấu hình email SMTP chỉ khi cần gửi email thật; mặc định phát triển dùng console backend.

## 3. Backup và khôi phục quy mô nhỏ

Lệnh `backup_db` tạo bản dump JSON, manifest SHA-256 và có thể sao chép media. Đây là tiện ích đơn giản cho demo/ứng dụng nhỏ; checksum chỉ phát hiện hỏng ngoài ý muốn, không phải chữ ký chống sửa đổi hay giải pháp backup database production thay thế nhà cung cấp.

```bash
python manage.py backup_db --dest /backups --include-media
python manage.py verify_backup /backups/20260918_120000  # thay bằng thư mục vừa tạo
```

Lưu bản sao ngoài máy/container, giới hạn quyền truy cập và mã hóa theo chính sách dữ liệu. Để xác minh restore trên database thử nghiệm cô lập:

```bash
BACKUP_DIR=/backups/20260918_120000  # thay bằng thư mục backup thực tế
python manage.py verify_backup "$BACKUP_DIR"
python manage.py migrate
python manage.py loaddata "$BACKUP_DIR/db.json"
```

Chỉ restore vào schema đã migrate và database thử nghiệm rỗng/cô lập; không nạp lặp fixture lên dữ liệu đang dùng. Nếu manifest cho biết có media, chép thư mục `media/` từ backup vào `MEDIA_ROOT` tương ứng trước khi smoke test. Với dịch vụ production thực, ưu tiên backup native/snapshot của database engine và diễn tập khôi phục theo hạ tầng đang chạy.

## 4. Kiểm tra trước khi triển khai

Các lệnh kiểm tra repository:

```bash
python -m pytest backend/summaries/tests/ -q
ruff check backend manage.py
ruff format --check backend manage.py
python manage.py check --deploy --fail-level ERROR
docker compose --env-file backend/.env config --quiet
```

CI kiểm tra Python 3.10–3.13, E2E, MySQL, SQL Server và Docker build. Việc đó không thay thế smoke test sau triển khai trên môi trường thật. Với một bản demo, kiểm tra đăng nhập, tạo tóm tắt TextRank, lịch sử, chia sẻ có hạn, upload, xuất file và health là đủ cơ bản. Kiểm tra PDF trên Windows cần Pango; CI Linux kiểm tra luồng này.

## 5. Lưu ý bảo mật tối thiểu

- Đặt `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` ngẫu nhiên và `DJANGO_ALLOWED_HOSTS` chỉ gồm host thực.
- Bảo vệ `API_ENCRYPTION_KEY`, `DB_PASSWORD`, `REDIS_PASSWORD` và Gemini key; không commit `.env`.
- Dùng TLS hợp lệ và cấu hình đúng proxy tin cậy; không tin header proxy từ client tùy ý.
- Áp dụng egress firewall cho webhook/URL fetch vì kiểm tra SSRF ứng dụng chưa loại bỏ hoàn toàn DNS rebinding.
- Thông báo rõ rằng chọn Gemini sẽ gửi nội dung tới Google; không dùng dữ liệu cá nhân/nhạy cảm cho demo.
- Đặt backup và media ngoài container, kiểm tra quyền truy cập và thử restore trước khi lưu dữ liệu cần giữ.

Xem thêm [README](../README.md), [chính sách bảo mật](SECURITY.md) và [kiến trúc](architecture.md).
