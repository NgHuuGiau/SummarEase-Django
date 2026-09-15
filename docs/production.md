# Runbook production

## 1. Cấu hình bắt buộc

Đặt các giá trị sau trong secret manager hoặc biến môi trường triển khai, không lưu vào Git:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<secret-ngau-nhien-it-nhat-50-ky-tu>
API_ENCRYPTION_KEY=<fernet-key>
DJANGO_ALLOWED_HOSTS=app.example.com
DB_ENGINE=sqlserver
REDIS_URL=redis://:<mat-khau>@redis:6379/0
```

Dùng database managed cho public deployment. SQLite chỉ phù hợp cho development hoặc hệ thống nội bộ một tiến trình.

## 2. Backup và khôi phục

Tạo backup database và media ít nhất mỗi ngày:

```bash
python manage.py backup_db --dest /backups --include-media
```

Mỗi backup gồm `db.json`, media tùy chọn và `manifest.json` chứa checksum SHA-256. Sao chép đầy đủ thư mục theo timestamp ra nơi lưu trữ bên ngoài host/container. Kiểm tra khôi phục hàng tháng trên database cô lập; backup chưa từng restore thì chưa được xác minh.

## 3. Health check và monitoring

- Probe `/health/` để kiểm tra database và media.
- Chỉ scrape `/metrics/` từ mạng monitoring; endpoint được bảo vệ trong production.
- Cảnh báo HTTP 5xx, latency, lỗi task Celery, độ dài hàng đợi, Redis, kết nối database, dung lượng đĩa và quota/lỗi Gemini.
- Đưa version triển khai và request/correlation ID vào hệ thống tập trung log.

## 4. Điều kiện release

Chạy trước khi deploy:

```bash
python -m pytest backend/summaries/tests.py -q
ruff check backend manage.py
ruff format --check backend manage.py
python manage.py check --deploy --fail-level ERROR
docker compose config --quiet
```

Chạy load test theo concurrency đỉnh dự kiến và review OWASP trước mỗi release public. Ghi lại kết quả và image/version dùng để rollback.

## 5. Khôi phục sự cố

1. Ngừng nhận traffic hoặc rollback về image cuối cùng đã biết là ổn định.
2. Lưu log và metrics trước khi restart worker.
3. Chỉ restore database sau khi xác minh checksum trong manifest.
4. Đối chiếu media với bản ghi database, sau đó chạy health check và smoke test.
5. Rotate secret bị lộ và ghi nhận sự cố.
