# Hướng dẫn đóng góp

Cảm ơn bạn đã quan tâm đến SummarEase. Đây là dự án demo/học tập; ưu tiên thay đổi nhỏ, dễ hiểu và phù hợp với phạm vi hiện tại.

## Chuẩn bị môi trường

Từ thư mục gốc repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
python manage.py setup
```

Có thể thay `3.12` bằng Python 3.10–3.13. Để chạy server, xem [README](../README.md) hoặc [hướng dẫn sử dụng](help.md). Không có tài khoản mặc định; đăng ký trên trang web hoặc chạy `python manage.py createsuperuser`.

## Trước khi gửi thay đổi

Chạy các kiểm tra phù hợp với phần đã sửa:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest backend/summaries/tests/ -q
ruff check backend manage.py
ruff format --check backend manage.py
```

Nếu thay đổi giao diện hoặc luồng người dùng, cài Chromium một lần và chạy E2E với server đang hoạt động ở terminal khác:

```bash
python -m playwright install chromium
```

```powershell
$env:BASE_URL = "http://127.0.0.1:8000"
python -m pytest frontend/e2e/test_home.py -q
```

Bash dùng `export BASE_URL="http://127.0.0.1:8000"`. Trên Windows, test xuất PDF có thể bỏ qua nếu thiếu Pango; môi trường CI Linux cài runtime này.

Workflow CI là nguồn chuẩn cho các cờ Ruff/mypy và thứ tự kiểm tra. Hiện CI kiểm tra Python 3.10–3.13, backend tests/coverage, Ruff, mypy, pip-audit, Playwright E2E, kiểm tra tích hợp MySQL/SQL Server và Docker build. Không cần chạy database tích hợp hoặc Docker cục bộ nếu chưa cài các dịch vụ đó; hãy nêu rõ phần nào chưa được xác minh.

## Nguyên tắc thay đổi

1. Giữ mỗi thay đổi tập trung vào một vấn đề; tránh thêm abstraction/dependency khi chưa có nhu cầu.
2. Giữ kiểm tra quyền, CSRF và xác thực dữ liệu ở backend; kiểm tra JavaScript chỉ là hỗ trợ giao diện.
3. Không commit khóa API, mật khẩu, cookie, `.env`, database/media hoặc chứng chỉ riêng.
4. Cập nhật tài liệu Markdown liên quan khi thay đổi tính năng, endpoint, cấu hình hay quy trình chạy.
5. Với endpoint hoặc database behavior mới, bổ sung test hồi quy phù hợp.
6. Dùng commit Conventional Commits khi thuận tiện, ví dụ `fix: sửa lỗi xác thực URL`, `docs: cập nhật hướng dẫn chạy demo`.

## Pull request

- Mô tả vấn đề và thay đổi bằng ngôn ngữ rõ ràng.
- Nêu lệnh test đã chạy cùng kết quả; không ghi test chưa thực hiện là đạt.
- Đính kèm ảnh khi thay đổi giao diện.
- Nêu giới hạn còn lại, đặc biệt phụ thuộc môi trường như Gemini API, Pango, Docker hoặc database ngoài.

## Quy ước mã nguồn

- Python: PEP 8, kiểm tra bằng Ruff.
- CSS: dùng quy ước hiện có trong `frontend/static/css/`.
- JavaScript: ES6+, camelCase.
- Template: Django template tags và quy ước hiện có trong `frontend/templates/`.
