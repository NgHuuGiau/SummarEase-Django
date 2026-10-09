# Gọi thử API bằng file HTTP

Thư mục này có `test.http` để gửi request bằng extension **REST Client** trong VS Code hoặc công cụ tương thích với định dạng HTTP file. Đây không phải collection Bruno dạng native; nếu dùng Bruno, cần tạo/import request theo định dạng Bruno.

## Chuẩn bị

1. Chạy ứng dụng từ thư mục gốc, ví dụ `python manage.py runserver 127.0.0.1:8000`.
2. Mở `test.http` và gửi các GET công khai như trang chủ, đăng nhập hoặc đăng ký.
3. Các request tạo tóm tắt, xem lịch sử/cài đặt và trang quản trị yêu cầu session hợp lệ. Đăng nhập trước và cung cấp cookie session cho HTTP client.
4. Với request POST, gửi thêm CSRF cookie và header `X-CSRFToken`; Django không cho phép bỏ CSRF chỉ để tiện thử API.

Ví dụ header cần thay bằng giá trị của session local hiện tại:

```http
Cookie: sessionid=<session-cookie>; csrftoken=<csrf-cookie>
X-CSRFToken: <csrf-cookie>
```

Không commit cookie, mật khẩu hoặc token thật. Các giá trị mẫu này không đại diện cho endpoint token-based; ứng dụng hiện dùng xác thực session cho các route giao diện/API này.

## Nội dung mẫu

File `test.http` có GET cho trang chủ, đăng nhập, đăng ký, lịch sử, cài đặt và admin; đồng thời có POST minh họa tạo tóm tắt TextRank/Gemini. Các POST chỉ chạy thành công khi đã đăng nhập, có CSRF hợp lệ và gửi đúng form fields. Request Gemini cần API key đã cấu hình ở hệ thống hoặc tài khoản; văn bản gửi tới Gemini sẽ được chuyển tới Google.

Tệp thử upload không vượt quá 10 MB và dùng định dạng được hỗ trợ: TXT, Markdown, DOCX, PDF hoặc EPUB. Chỉ thử URL công khai mà bạn được phép truy cập; server chặn các đích mạng nội bộ.

## Lưu ý

- POST/PUT/DELETE cần session và CSRF khi dùng cookie-based authentication.
- Không dùng tài khoản hoặc API key thật của người khác.
- Không lưu cookie, secret, mật khẩu hoặc dữ liệu cá nhân vào file request đã theo dõi bằng Git.
- File request hiện là ví dụ thủ công, không tự đăng nhập hay cấp CSRF token.
