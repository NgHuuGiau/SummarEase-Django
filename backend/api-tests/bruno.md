# Kiểm thử API (Bruno)

Dùng `test.http` trong thư mục này để gọi nhanh các endpoint của backend Django.

## Chuẩn bị

1. Khởi động hệ thống bằng `scripts/run-dev.ps1` hoặc `python manage.py runserver`.
2. Đăng nhập bằng tài khoản local và giữ lại cookie phiên đăng nhập.
3. Gửi CSRF token kèm cookie khi gọi các endpoint POST/PUT/DELETE.

## Lưu ý

- Endpoint tạo bản tóm tắt cần đăng nhập.
- Các endpoint thay đổi dữ liệu cần CSRF token và session cookie.
- Không ghi API key, mật khẩu hoặc cookie thật vào collection trước khi commit.
