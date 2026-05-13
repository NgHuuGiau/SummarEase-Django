# Hướng dẫn chạy SummarEase Django Rebuild

## Tổng quan

Đây là phiên bản mới của SummarEase, không dùng PHP. Toàn bộ hệ thống được tổ chức lại thành:

- `backend/`: Django, Python, ORM, auth, API, xử lý tóm tắt
- `frontend/`: HTML, CSS, JavaScript
- `sql/`: schema MySQL và file SQLite
- `docker/`: cấu hình chạy container
- `testsAPI/`: file gọi API để test nhanh

## Chạy local

### Yêu cầu

- Python 3.12+
- `pip`
- MySQL 8+ nếu muốn chạy MySQL

### Cài đặt

```bash
cd D:\Downloads\SummarEase_Django
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy backend\.env.example backend\.env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Database

### Mặc định

- Dùng SQLite
- Tệp cơ sở dữ liệu sẽ nằm tại `sql/db.sqlite3`

### Chuyển sang MySQL

Sửa `backend/.env`:

```env
DB_ENGINE=mysql
DB_NAME=summarease_django
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
```

Sau đó chạy:

```bash
python manage.py migrate
```

## Endpoint chính

- `GET /`: trang chủ
- `POST /api/summaries/create/`: tạo bản tóm tắt
- `GET /history/`: lịch sử của người đăng nhập
- `GET /history/<id>/`: chi tiết bản tóm tắt
- `POST /history/<id>/delete/`: xóa bản tóm tắt
- `GET /admin/`: trang admin Django

