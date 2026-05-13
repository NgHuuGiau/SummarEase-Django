# Kiến trúc thư mục

```text
SummarEase_Django/
|-- backend/
|   |-- config/
|   |-- summaries/
|   |-- requirements.txt
|   `-- .env.example
|-- frontend/
|   |-- static/
|   `-- templates/
|-- sql/
|   |-- schema_mysql.sql
|   `-- db.sqlite3
|-- docker/
|   |-- Dockerfile-python
|   |-- Dockerfile-mysql
|   `-- docker-compose.yml
|-- docs/
|-- testsAPI/
|-- manage.py
`-- requirements.txt
```

## Mapping với dự án cũ

- `backendPHP` và `backendNLP` được gộp thành `backend/`
- `resources/views` và `public/build` được thay bằng `frontend/templates` và `frontend/static`
- `MySQL/` được thay bằng `sql/`
- `docker/`, `docs/`, `testsAPI/` vẫn giữ vai trò tương tự
