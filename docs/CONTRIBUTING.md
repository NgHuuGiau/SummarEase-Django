# Hướng Dẫn Đóng Góp

Cảm ơn bạn quan tâm đến việc đóng góp cho **SummarEase Django**! 🎉

## Thiết lập môi trường phát triển

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python manage.py setup
python manage.py runserver
```

## Quy tắc khi đóng góp

1. **Giữ phạm vi thay đổi nhỏ, rõ ràng** — mỗi PR chỉ nên giải quyết một vấn đề
2. **Chạy kiểm tra trước khi gửi PR**

   ```powershell
   python manage.py check
   python -m pytest backend/summaries/tests.py -q
   ruff check backend manage.py
   ruff format --check backend manage.py
   mypy backend manage.py --ignore-missing-imports --follow-imports=skip
   python manage.py check --deploy --fail-level ERROR
   ```

3. **Chạy E2E khi thay đổi giao diện hoặc luồng người dùng**. Mở server ở terminal riêng rồi chạy:

   ```powershell
   python manage.py migrate
   python manage.py runserver 127.0.0.1:8000
   $env:BASE_URL = "http://127.0.0.1:8000"
   python -m pytest frontend/e2e/test_home.py -q
   ```

   Cài Chromium cho Playwright nếu môi trường chưa có: `playwright install chromium`.

4. **Tự kiểm tra API bị ảnh hưởng** bằng Django tests hoặc collection trong `backend/api-tests/`.
5. **Cập nhật tài liệu Markdown liên quan** nếu thay đổi hành vi, endpoint, cấu hình, kiểm thử hoặc quy trình triển khai.

CI trên GitHub Actions kiểm tra Python 3.10–3.13, Django tests/coverage, Ruff, mypy, pip-audit, Playwright E2E, cú pháp JavaScript, manifest và build/deploy checks. Hãy chạy các kiểm tra liên quan trước khi mở PR.

## Khi viết Pull Request

- Mô tả rõ vấn đề đang giải quyết
- Tóm tắt cách triển khai
- Đính kèm ảnh chụp màn hình nếu có thay đổi giao diện
- Nêu rõ rủi ro, giới hạn hiện tại hoặc việc cần làm tiếp
- Nêu test đã chạy và kết quả; không ghi kết quả chưa được xác minh

## Code style

- Python: theo PEP 8 (tự động kiểm tra bằng Ruff)
- CSS: 2 spaces indent, class-based naming
- JavaScript: ES6+, camelCase
- Template: Django template tags, 2 spaces indent
