# Chính sách bảo mật

## Báo cáo lỗ hổng

Vui lòng **không đăng chi tiết lỗ hổng chưa được khắc phục trong issue công khai**. Hãy dùng tính năng báo cáo lỗ hổng riêng tư của repository trên GitHub nếu tính năng này được bật; nếu không, liên hệ chủ repository qua kênh riêng. Chỉ gửi thông tin cần thiết để tái hiện, tác động và đề xuất khắc phục; không đính kèm dữ liệu người dùng hoặc bí mật thật.

## Phạm vi

Các khu vực cần được chú ý khi thay đổi hoặc kiểm thử:

- Đăng ký, đăng nhập, khóa đăng nhập và phân quyền dữ liệu theo chủ sở hữu.
- Tải lên, giải nén và trích xuất nội dung tài liệu.
- Nhập URL từ người dùng và các request server-to-server (Gemini, webhook).
- Quản lý session, CSRF, khóa API và biến môi trường.
- Chia sẻ công khai bằng token, API, health check và metrics.

## Biện pháp trong mã nguồn

- Django session authentication, CSRF middleware và kiểm tra quyền ở backend.
- Lịch sử, bản tóm tắt và webhook được giới hạn theo người dùng (ngoại lệ staff có chủ đích).
- Upload giới hạn 10 MB cho từng tệp, allowlist TXT/Markdown/DOCX/PDF/EPUB và kiểm tra lại ở server.
- URL nhập vào được kiểm tra địa chỉ IP, redirect, timeout và kích thước phản hồi; request không dùng proxy lấy từ môi trường.
- Webhook ở production yêu cầu HTTPS, từ chối địa chỉ riêng/tên đăng nhập trong URL và không theo redirect.
- Khóa Gemini cá nhân được mã hóa trong database; khi gọi Gemini, backend gửi khóa qua header API thay vì query string.
- CSRF, CSP và các security headers được cấu hình trong Django middleware.
- Tạo tóm tắt bị giới hạn tần suất; đăng nhập có giới hạn thử sai dựa trên cache.
- Trong production, `/metrics/` chỉ trả dữ liệu cho staff; `/health/` trả trạng thái tổng quát của database/media.
- `.env`, media, SQLite local và chứng chỉ phát triển được loại khỏi Git theo `.gitignore`; đặt backup ngoài repository và kiểm tra trước khi commit.

Đây là mô tả các biện pháp trong repository, không phải chứng nhận bảo mật hay kết quả kiểm thử xâm nhập độc lập. Hãy xem test bảo mật hiện có và xác minh lại sau khi thay đổi luồng liên quan.

## Giới hạn và triển khai

- TextRank chạy nội bộ; khi người dùng chọn Gemini, nội dung được gửi đến dịch vụ Google. Không gửi dữ liệu nhạy cảm nếu chưa có đánh giá quyền riêng tư phù hợp.
- Kiểm tra URL trong ứng dụng giảm SSRF nhưng không loại bỏ hoàn toàn rủi ro DNS rebinding. Với dịch vụ công khai, áp dụng egress firewall/network policy để chặn loopback, mạng riêng, link-local và metadata endpoints.
- Rate limit dựa trên cache local chỉ chia sẻ giữa các worker nếu cấu hình cache dùng chung (ví dụ Redis). Không coi giới hạn local là kiểm soát chống lạm dụng đủ cho hệ thống public.
- Chứng chỉ tự ký của script Windows chỉ dành cho phát triển. Production cần TLS hợp lệ ở reverse proxy/load balancer, chỉ cho proxy tin cậy truy cập ứng dụng và đặt `TRUSTED_PROXY_IPS` chính xác.
- Không dùng `DJANGO_DEBUG=True`, khóa mặc định, `ALLOWED_HOSTS=*`, tài khoản demo hoặc secrets trong Git khi triển khai.
- Với Docker Compose production, cấu hình secret manager, MySQL/SQL Server bên ngoài, Redis trong mạng riêng, quyền truy cập media và backup/khôi phục trước khi nhận dữ liệu thật.

Nếu nghi ngờ secret bị lộ, thu hồi/rotate secret liên quan, kiểm tra log và hoạt động truy cập, rồi mới tiếp tục sử dụng dịch vụ.
