# Chính Sách Bảo Mật

## Báo cáo lỗ hổng

Nếu bạn phát hiện vấn đề bảo mật, **không tạo issue công khai**. Vui lòng gửi riêng cho người duy trì dự án các thông tin sau:

- Mô tả ngắn gọn nhưng rõ ràng về lỗ hổng
- Các bước tái hiện
- Mức độ ảnh hưởng
- Hướng khắc phục đề xuất (nếu có)

## Phạm vi ưu tiên

- Xác thực và phân quyền
- Quyền truy cập khu quản trị
- Tải tệp lên và xử lý nội dung tệp
- Nhập dữ liệu từ URL hoặc nguồn bên ngoài
- Quản lý biến môi trường, khoá bí mật và cấu hình hệ thống

## Các biện pháp hiện tại

- ✅ API key gửi qua header thay vì URL query param
- ✅ `html.escape()` ngăn XSS trong highlight keyword
- ✅ CSRF protection của Django
- ✅ File upload validate loại file, tự động xoá khi xoá Document
- ✅ Rate limiting 5s giữa các request tóm tắt
- ✅ API key người dùng được mã hoá trong database
- ✅ `.env` và `certs/` nằm trong `.gitignore`
