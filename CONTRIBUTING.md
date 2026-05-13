# Hướng Dẫn Đóng Góp

Cảm ơn bạn đã muốn đóng góp cho `SummarEase Django`.

## Thiết lập môi trường phát triển

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Trước khi tạo Pull Request

1. Giữ phạm vi thay đổi nhỏ, rõ ràng và bám đúng mục tiêu.
2. Chạy kiểm tra cục bộ trước khi gửi PR.
3. Tự kiểm tra lại giao diện hoặc API bị ảnh hưởng.
4. Cập nhật tài liệu nếu thay đổi làm khác hành vi hoặc cách cài đặt.

## Các lệnh nên chạy

```powershell
python manage.py check
python manage.py test summaries
```

## Khi viết Pull Request

- Mô tả rõ vấn đề đang giải quyết.
- Tóm tắt cách triển khai.
- Đính kèm ảnh chụp màn hình nếu có thay đổi giao diện.
- Nêu rõ rủi ro, giới hạn hiện tại hoặc việc cần làm tiếp.

