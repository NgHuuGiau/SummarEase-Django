# SummarEase Django

SummarEase Django là phiên bản xây dựng lại hệ thống tóm tắt nội dung bằng Django, tập trung vào trải nghiệm web, lưu lịch sử người dùng và khu quản trị dành cho admin.

## Công nghệ sử dụng

- Python 3.12
- Django
- HTML, CSS, JavaScript
- SQLite mặc định, hỗ trợ MySQL nếu cần

## Tính năng chính

- Đăng ký, đăng nhập, đăng xuất
- Tóm tắt từ văn bản, tệp hoặc URL
- Hỗ trợ nhiều phương pháp tóm tắt như `TextRank` và `Gemini`
- Lưu lịch sử tóm tắt theo tài khoản
- Xem chi tiết nội dung gốc và bản tóm tắt đã lưu
- Phân quyền cơ bản giữa người dùng và quản trị viên
- Giao diện sáng/tối cho khu người dùng và admin

## Cấu trúc thư mục

- `backend/`: mã nguồn Django
- `backend/config/`: cấu hình dự án như `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`
- `backend/summaries/`: app chính cho chức năng tóm tắt
- `frontend/templates/`: template HTML
- `frontend/static/`: CSS và JavaScript
- `sql/`: schema tham khảo và file SQLite
- `media/`: dữ liệu người dùng tải lên trong lúc chạy
- `testsAPI/`: file test API thủ công
- `docker/`: cấu hình Docker
- `docs/`: tài liệu bổ sung

## Yêu cầu môi trường

- Python 3.12 trở lên được khuyến nghị
- Windows PowerShell, Command Prompt hoặc terminal tương đương

## Hướng dẫn chạy dự án

### 1. Di chuyển vào thư mục dự án

```powershell
cd D:\Downloads\SummarEase_Django
```

### 2. Tạo môi trường ảo

```powershell
python -m venv .venv
```

### 3. Kích hoạt môi trường ảo

```powershell
.\.venv\Scripts\activate
```

Nếu PowerShell chặn script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\activate
```

### 4. Cài đặt thư viện

```powershell
pip install -r requirements.txt
```

### 5. Cấu hình môi trường

Nếu dự án có file mẫu `.env`, hãy sao chép và chỉnh lại theo nhu cầu:

```powershell
copy backend\.env.example backend\.env
```

Nếu chưa có file mẫu, bạn có thể tự tạo `backend/.env` để cấu hình các giá trị như khóa `GEMINI_API_KEY` hoặc thông tin MySQL.

### 6. Chạy migrate

```powershell
python manage.py migrate
```

Với cấu hình mặc định, file SQLite sẽ được tạo tại:

```text
sql/db.sqlite3
```

### 7. Tạo tài khoản quản trị

```powershell
python manage.py createsuperuser
```

### 8. Chạy dự án

```powershell
python manage.py runserver
```

Sau đó truy cập:

```text
http://127.0.0.1:8000/
```

Khu quản trị:

```text
http://127.0.0.1:8000/admin/
```

## Chạy kiểm tra

```powershell
python manage.py check
python manage.py test summaries
```

## Cấu hình cơ sở dữ liệu

### Mặc định: SQLite

Không cần chỉnh thêm nếu bạn chỉ muốn chạy nhanh dự án cục bộ.

### Tùy chọn: MySQL

Thêm hoặc chỉnh các biến trong `backend/.env`:

```env
DB_ENGINE=mysql
DB_NAME=summarease_django
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
```

Sau đó chạy lại:

```powershell
python manage.py migrate
```

## Một số lệnh hữu ích

```powershell
python manage.py check
python manage.py test summaries
python manage.py createsuperuser
python manage.py runserver
```

## Khi gặp lỗi

- Lỗi `No module named django`: chưa kích hoạt `.venv` hoặc chưa cài thư viện.
- Lỗi PowerShell không cho activate: dùng `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- Lỗi liên quan đến Gemini: kiểm tra lại `GEMINI_API_KEY` trong `backend/.env`.
- Lỗi MySQL: kiểm tra `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` và bảo đảm MySQL đang chạy.

## Đóng góp

Nếu muốn đóng góp, hãy xem thêm tại [CONTRIBUTING.md](CONTRIBUTING.md).

## Bảo mật

Nếu phát hiện vấn đề bảo mật, hãy xem hướng dẫn tại [SECURITY.md](SECURITY.md).
