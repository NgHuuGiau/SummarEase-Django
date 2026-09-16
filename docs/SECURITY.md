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
- ✅ `.env`, media, backup và chứng chỉ nằm trong `.gitignore`
- ✅ SSRF chặn mạng nội bộ, redirect không an toàn và proxy môi trường
- ✅ Webhook production yêu cầu HTTPS, từ chối mạng riêng và không theo redirect
- ✅ Giới hạn upload, URL response và ZIP extraction
- ✅ Metrics được bảo vệ trong production
- ✅ Kiểm tra dữ liệu trên giao diện để phản hồi sớm; Django forms/services vẫn xác thực lại ở backend
- ✅ Giới hạn kích thước file upload ở 10 MB và allowlist phần mở rộng (`.txt`, `.md`, `.markdown`, `.docx`, `.pdf`, `.epub`)

## Giới hạn và trách nhiệm triển khai

Kiểm tra phía trình duyệt chỉ nhằm cải thiện trải nghiệm, không phải ranh giới bảo mật; mọi dữ liệu nhận từ client phải tiếp tục được xác thực ở server. Các biện pháp trên không thay thế penetration test độc lập. Production phải dùng secret manager, database có backup ngoài container, Redis private network, egress firewall chặn mạng nội bộ và monitoring có cảnh báo. Chỉ tin `X-Forwarded-For` từ proxy được khai báo trong `TRUSTED_PROXY_IPS`; đặt TLS termination ở proxy tin cậy và chặn truy cập trực tiếp từ Internet vào cổng ứng dụng. Khi nghi ngờ lộ secret, hãy rotate secret trước khi điều tra chi tiết.
