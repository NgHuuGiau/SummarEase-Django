# Kiểm thử API (Bruno)

Dùng `test.http` trong thư mục này với Bruno hoặc REST Client tương thích để gọi nhanh các endpoint của backend Django. Request tạo tóm tắt yêu cầu phiên đăng nhập hợp lệ.

## Chuẩn bị

1. Khởi động hệ thống bằng `scripts/run-dev.ps1` hoặc `python manage.py runserver`.
2. Đăng nhập bằng tài khoản local và giữ lại cookie phiên đăng nhập.
3. Gửi CSRF token kèm cookie khi gọi các endpoint POST/PUT/DELETE.

Endpoint tạo tóm tắt chấp nhận nguồn văn bản, URL hoặc tệp; phương thức và tỷ lệ cũng được kiểm tra ở server. Khi thử upload, dùng tệp kiểm thử không nhạy cảm, nhỏ hơn 10 MB và có phần mở rộng được hỗ trợ.

## Lưu ý

- Endpoint tạo bản tóm tắt cần đăng nhập.
- Các endpoint thay đổi dữ liệu cần CSRF token và session cookie.
- Không ghi API key, mật khẩu hoặc cookie thật vào collection trước khi commit.
