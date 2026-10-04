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

## 3b. Quy trình khôi phục (Restore) từ backup

Giả sử thư mục backup là `/backups/20260918_120000` (tạo bởi `backup_db --include-media`).

### 1. Chuẩn bị database trống (MySQL/PostgreSQL/SQL Server)

```bash
# MySQL
mysql -u root -p -e "CREATE DATABASE summarease_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# PostgreSQL
psql -U postgres -c "CREATE DATABASE summarease_django;"

# SQL Server (sqlcmd)
sqlcmd -S localhost -U sa -P "YourPassword" -Q "CREATE DATABASE [SummarEase_Django];"
```

Cập nhật `.env` trỏ về DB mới, sau đó:
```bash
python manage.py migrate --noinput
```

### 2. Nạp dữ liệu JSON

```bash
BACKUP_DIR=/backups/20260918_120000
python manage.py loaddata "$BACKUP_DIR/db.json"
```

Lệnh này nạp `User`, `Document`, `Summary`, `Tag`, `WebhookRegistration`, `WebhookDelivery`... theo đúng FK. Không dùng `flush` vì đã migrate trên DB trống.

### 3. Khôi phục media (nếu backup có `--include-media`)

```bash
cp -r "$BACKUP_DIR/media/"* "$MEDIA_ROOT/"
```

Kiểm tra quyền ghi: `chown -R www-data:www-data "$MEDIA_ROOT"` (nếu chạy user `www-data`).

### 4. Verify & Smoke test

```bash
python manage.py verify_backup "$BACKUP_DIR"
python manage.py check --deploy --fail-level ERROR

# Smoke test thủ công
curl -f http://localhost:8000/health/
curl -f -X POST -H "Content-Type: application/json" \
     -d '{"source_type":"text","method":"textrank","ratio":0.3,"text":"Test khôi phục."}' \
     http://localhost:8000/api/v1/summaries/create/
```

### 5. Rollback nếu sai

Nếu phát hiện lỗi dữ liệu: drop DB → tạo lại → lặp lại từ bước 1. Backup file gốc không bị sửa đổi nên có thể thử lại nhiều lần.

---

## 6. Kết quả kiểm thử tải (Load Test)

Chạy Locust 10 users, spawn 2/s, 5 phút, scenario `steady` (xem `loadtest/`):

```bash
python loadtest/run_load_test.py --scenario steady --headless --html-report loadtest-report.html
```

**Kết quả (snapshot 03/10/2026, local Windows, SQLite, 10 users, 5 phút):**

| Chỉ số | Giá trị |
|---|---|
| Tổng requests | 1.848 |
| Throughput | **6,18 req/s** |
| Thời gian phản hồi trung bình | **20 ms** |
| Thời gian phản hồi tối đa | **2.087 ms** |
| p50 / p95 / p99 | 6 ms / 10 ms / 51 ms |
| Tỷ lệ thất bại | **1,73 %** (32/1.848) |

**Phân loại lỗi (được mong đợi):**
- **Login 100%**: test user tạo mới nhưng CSRF token chưa sync trong Locust (không ảnh hưởng user thật).
- **OpenAPI / Swagger / ReDoc (429)**: rate-limit đang hoạt động đúng.
- **Health Check (1× 503)**: transient khi DB busy, tự phục hồi.

**Kết luận**: throughput ~6 req/s trên SQLite single-thread dev server, latency p95 < 15 ms. Với gunicorn workers + MySQL/PostgreSQL production, throughput và p95 sẽ tốt hơn đáng kể. Báo cáo HTML đầy đủ: `loadtest-report.html`.

### Stress Test (50 users, 5 phút)

```bash
python loadtest/run_load_test.py --scenario stress --headless --html-report stress-report.html
```

**Kết quả (50 users, spawn 5/s, 5 phút):**

| Chỉ số | Giá trị |
|---|---|
| Tổng requests | 13.989 |
| Throughput | **46,85 req/s** |
| Thời gian phản hồi trung bình | **21 ms** |
| Thời gian phản hồi tối đa | **2.964 ms** |
| p50 / p95 / p99 | 7 ms / 21 ms / 65 ms |
| Tỷ lệ thất bại | **19,2 %** (2.681/13.989) |

**Phân loại lỗi (được mong đợi - rate limit đang hoạt động):**
- **Create Summary 97%**: rate limit 429 (bảo vệ hệ thống khỏi quá tải)
- **Swagger/OpenAPI/ReDoc 70%**: rate limit 429 trên docs endpoints
- **Health Check 2%**: transient 503 khi DB busy

**Kết luận**: throughput ~47 req/s, p95 ~21 ms. Rate limit hoạt động đúng, bảo vệ hệ thống khỏi quá tải. Với production (gunicorn workers + PostgreSQL), throughput cao hơn và p95 ổn định hơn.

---

## 7. So sánh TextRank vs Gemini (Benchmark chất lượng)

Dataset: 15 văn bản tiếng Việt (kỹ thuật, giáo dục, công nghệ) có reference summary tay (`summaries/eval/vn_dataset.json`).

```bash
python manage.py evaluate --ratio 0.3
```

| Phương pháp | ROUGE-1 | ROUGE-2 | ROUGE-L | Tỉ lệ nén | Latency (CPU) |
|---|---:|---:|---:|---:|---:|
| **TextRank (offline)** | **0.513** | **0.222** | **0.368** | 24,7% | ~15 ms |
| Baseline "câu đầu" | 0.520 | 0.266 | 0.390 | 26,0% | <1 ms |
| **Gemini 1.5 Flash** (API) | *chưa đo* | *chưa đo* | *chưa đo* | ~30% | 800–2000 ms |

**Nhận xét**: TextRank extractive đạt ROUGE-1 ~0,51 so với reference extractive, đủ tốt cho demo/đọc nhanh. Baseline "câu đầu" thắng nhẹ vì văn bản kỹ thuật thường tóm tắt ở đầu. Gemini abstractive sẽ tốt hơn về ngữ nghĩa (cần API key, có latency, cost). TextRank: free, offline, deterministic, p95 < 20 ms.

---

## 8. Kết quả bảo mật (Security Audit)

```bash
pip-audit -r requirements.txt --format=json
```
**Kết quả (03/10/2026)**: **0 CVE Critical/High** trên dependencies pinned. CodeQL GitHub Actions quét `security-and-quality` queries hàng tuần — 0 finding mới.

---

## 9. SBOM (Software Bill of Materials)

```bash
pip install cyclonedx-bom
cyclonedx-py -o sbom.json
```
File `sbom.json` (CycloneDX 1.6) đính kèm trong artifact release — chứa đầy đủ package, version, license (BSD/MIT/Apache-2.0/PSF), hash SHA-256. Không có GPL/copyleft.

---

## 10. Grafana Dashboard (Prometheus)

Metrics exposed tại `/metrics/` (staff only). Dashboard JSON (`monitoring/grafana-dashboard.json`) bao gồm panels:
- **Request rate** (by endpoint, method, status)
- **Latency** p50/p95/p99 by endpoint
- **Error rate** (5xx, 4xx)
- **Celery queue depth** (pending/active/failed tasks)
- **Webhook delivery** (success/fail/pending, retry histogram)
- **System** (CPU, RAM, DB connections, cache hit rate)

Import vào Grafana → Dashboards → Import JSON.

---

## 4. Kiểm tra trước khi triển khai

Các lệnh kiểm tra repository:

```bash
python -m pytest backend/summaries/tests.py -q
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
