# Runbook production

## 1. Cấu hình bắt buộc

Đặt các giá trị sau trong secret manager hoặc biến môi trường triển khai, không lưu vào Git:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<secret-ngau-nhien-it-nhat-50-ky-tu>
API_ENCRYPTION_KEY=<fernet-key>
DJANGO_ALLOWED_HOSTS=app.example.com
DB_ENGINE=sqlserver
DB_DRIVER=ODBC Driver 18 for SQL Server
REDIS_PASSWORD=<mat-khau-url-safe>
LOG_FORMAT=json
# TRUSTED_PROXY_IPS=<CIDR-cua-proxy-neu-co>
```

Compose chạy Gunicorn, Celery worker và Celery Beat riêng, vì vậy chỉ chấp nhận MySQL hoặc SQL Server dùng chung; SQLite không được mount/persist trong cấu hình này. Celery Beat quét outbox webhook mỗi phút để khôi phục các lần enqueue thất bại hoặc worker bị gián đoạn. Docker image cài ODBC Driver 18 cho SQL Server; khi dùng SQL Server, giữ `DB_DRIVER=ODBC Driver 18 for SQL Server`. Redis nội bộ được bảo vệ bằng `REDIS_PASSWORD`; Compose tự tạo `REDIS_URL` có xác thực cho web, worker và Beat. Sinh mật khẩu URL-safe bằng `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Đặt `DB_HOST` tới database có thể truy cập từ container và `DJANGO_ALLOWED_HOSTS` là hostname thật (không dùng localhost). Chạy Compose bằng `docker compose --env-file backend/.env up --build` để Compose đọc các biến cấu hình.

Compose chưa cung cấp TLS termination. Đặt reverse proxy/load balancer HTTPS phía trước, chỉ cho proxy truy cập cổng ứng dụng `8000`, và khai báo IP/CIDR proxy trong `TRUSTED_PROXY_IPS`. Để trống biến này nếu ứng dụng không đứng sau proxy.

Sinh khóa riêng bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"` rồi lưu trong secret manager. `API_ENCRYPTION_KEY` phải được giữ ổn định và backup riêng: đổi khóa khi đã mã hóa API key người dùng sẽ khiến dữ liệu cũ không giải mã được. Thay khóa chỉ sau khi có kế hoạch giải mã/mã hóa lại dữ liệu và kiểm thử khôi phục.

## 2. Backup và khôi phục

Tạo backup database và media ít nhất mỗi ngày:

```bash
python manage.py backup_db --dest /backups --include-media
```

Mỗi backup gồm `db.json`, media tùy chọn và `manifest.json` chứa checksum SHA-256. Sao chép đầy đủ thư mục theo timestamp ra nơi lưu trữ bên ngoài host/container; mã hóa backup khi lưu và giới hạn quyền truy cập. Checksum phát hiện hỏng dữ liệu ngoài ý muốn, không phải chữ ký chống sửa đổi có chủ đích. Kiểm tra tính toàn vẹn trước khi khôi phục; lệnh này không thay thế việc restore. Khôi phục hàng tháng trên database cô lập, rỗng:

```bash
BACKUP_DIR=/backups/20260917_120000
python manage.py verify_backup "$BACKUP_DIR"
python manage.py loaddata "$BACKUP_DIR/db.json"
```

Sau đó xác minh ứng dụng và đối chiếu media. Backup chưa từng restore thì chưa được xác minh.

Nếu đã backup media, khôi phục thư mục đó vào `MEDIA_ROOT` trước khi smoke test:

```bash
if [ -d "$BACKUP_DIR/media" ]; then
  mkdir -p "$MEDIA_ROOT"
  cp -a "$BACKUP_DIR/media/." "$MEDIA_ROOT/"
fi
```

## 3. Health check và monitoring

- Probe `/health/` để kiểm tra database và media.
- Chỉ scrape `/metrics/` từ mạng monitoring; endpoint được bảo vệ trong production. `/health/` trả thông tin lỗi tổng quát; chi tiết nằm trong log.
- Cảnh báo HTTP 5xx, latency, lỗi task Celery, độ dài hàng đợi, Redis, kết nối database, dung lượng đĩa và quota/lỗi Gemini.
- Theo dõi webhook outbox ở trạng thái pending lâu bất thường hoặc failed; khi khôi phục từ sự cố, đối tác nên khử trùng lặp theo header `X-Webhook-Delivery` (giao nhận là at-least-once, không thể bảo đảm exactly-once qua HTTP).
- Ứng dụng xuất structured JSON log ra stdout trong production; thu thập stdout từ web/worker vào hệ thống log tập trung, lưu version triển khai và `X-Request-ID` để truy vết.
- Tạo cảnh báo tại nền tảng giám sát cho 5xx, p95 latency, health check thất bại, task Celery lỗi/tồn đọng, database/Redis không sẵn sàng, disk còn dưới 15% và lỗi/quota Gemini; định tuyến cảnh báo tới người trực vận hành. Các tích hợp này phụ thuộc nền tảng triển khai, chưa được tự động tạo bởi repository.
- Webhook chỉ gửi tới địa chỉ công khai và không theo redirect; vẫn cấu hình egress firewall để chặn loopback, mạng riêng và metadata endpoint, phòng DNS rebinding.

## 4. Điều kiện release

Chạy trước khi deploy:

```bash
python -m pytest backend/summaries/tests.py -q
ruff check backend manage.py
ruff format --check backend manage.py
python manage.py check --deploy --fail-level ERROR
docker compose config --quiet
```

Với Compose production, dùng `docker compose --env-file backend/.env config --quiet`. CI kiểm tra deploy settings, validate Compose và build Docker image; test backend cũng kiểm tra khôi phục fixture vào SQLite cô lập. Trước khi chạy production, vẫn cần diễn tập backup/restore trên đúng engine MySQL hoặc SQL Server đang dùng.

CI chạy webhook/migration integration trên MySQL 8.4 và SQL Server 2022 với ODBC Driver 18, cùng E2E Playwright trên Chromium. Trước khi phát hành, vẫn diễn tập trên đúng phiên bản/driver production và thực hiện smoke test desktop/mobile. Xác minh upload các định dạng được hỗ trợ, tải file xuất, chia sẻ có thời hạn, đăng nhập, cài đặt, khôi phục mật khẩu và phân quyền. Không dùng dữ liệu hoặc API key thật trong test.

Chạy load test theo concurrency đỉnh dự kiến và review OWASP trước mỗi release public. Ghi lại kết quả và image/version dùng để rollback.

## 5. Khôi phục sự cố

1. Ngừng nhận traffic hoặc rollback về image cuối cùng đã biết là ổn định.
2. Lưu log và metrics trước khi restart worker.
3. Chỉ restore database sau khi xác minh checksum trong manifest.
4. Đối chiếu media với bản ghi database, sau đó chạy health check và smoke test.
5. Rotate secret bị lộ và ghi nhận sự cố.
