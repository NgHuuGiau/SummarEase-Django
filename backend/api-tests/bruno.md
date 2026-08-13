# API Test (Bruno)

Dùng `test.http` để gọi nhanh các endpoint của backend Django.

## Lưu ý

- Endpoint tạo bản tóm tắt cần đăng nhập nếu dùng trong trình duyệt
- Nếu dùng client API, cần gửi CSRF token và session cookie để test đầy đủ luồng xác thực của Django
