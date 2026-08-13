# Hướng Dẫn Đóng Góp

Cảm ơn bạn quan tâm đến việc đóng góp cho **SummarEase Django**! 🎉

## Thiết lập môi trường phát triển

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py setup
python manage.py runserver
```

## Quy tắc khi đóng góp

1. **Giữ phạm vi thay đổi nhỏ, rõ ràng** — mỗi PR chỉ nên giải quyết một vấn đề
2. **Chạy kiểm tra trước khi gửi PR**

   ```powershell
   python manage.py check
   python manage.py test summaries
   ```

3. **Tự kiểm tra giao diện hoặc API bị ảnh hưởng**
4. **Cập nhật tài liệu** nếu thay đổi làm khác hành vi hoặc cách cài đặt

## Khi viết Pull Request

- Mô tả rõ vấn đề đang giải quyết
- Tóm tắt cách triển khai
- Đính kèm ảnh chụp màn hình nếu có thay đổi giao diện
- Nêu rõ rủi ro, giới hạn hiện tại hoặc việc cần làm tiếp

## Code style

- Python: theo PEP 8 (tự động kiểm tra bằng Ruff)
- CSS: 2 spaces indent, class-based naming
- JavaScript: ES6+, camelCase
- Template: Django template tags, 2 spaces indent
