# Hướng dẫn quay video demo SummarEase (3 phút)

## Chuẩn bị (trước khi quay)
```bash
# 1. Khởi động ứng dụng
python manage.py seed_demo --clear
python manage.py runserver 127.0.0.1:8000

# 2. Mở browser tại http://127.0.0.1:8000
# 3. Chuẩn bị sẵn:
#    - Văn bản test (copy từ vn_dataset.json)
#    - File PDF/DOCX test (nếu có)
#    - URL test: https://vnexpress.net/giao-duc/du-hoc-sinh-viet-nam-tang-manh-4721234.html
```

---

## Kịch bản quay (3:00)

### 0:00–0:15 | Giới thiệu & Đăng nhập
- **Mở trang chủ** → chỉ title "SummarEase - Tóm tắt văn bản thông minh với AI"
- **Click "Đăng nhập"** → nhập `demo` / `demo123456` (tạo bởi `seed_demo`)
- **Nói**: "Đăng nhập bằng tài khoản demo có sẵn 3 tài liệu mẫu"

### 0:15–0:45 | Tóm tắt văn bản (TextRank)
- **Chọn "Văn bản"** → dán đoạn văn bản dài (copy từ `vn_dataset.json` item `vn_01` về Django)
- **Chọn "TextRank"**, ratio 0.3 → **Nhấn "Tóm tắt"**
- **Chờ loading** → hiện kết quả: summary, keywords, sentences
- **Nói**: "TextRank chạy offline, ~2ms, không cần API key"

### 0:45–1:15 | Tóm tắt URL
- **Chọn "URL"** → dán: `https://vnexpress.net/giao-duc/du-hoc-sinh-viet-nam-tang-manh-4721234.html`
- **Chọn TextRank**, ratio 0.2 → **Tóm tắt**
- **Nói**: "Hệ thống tự trích xuất nội dung từ URL, kiểm tra SSRF, loại bỏ quảng cáo/nav"

### 1:15–1:45 | Upload file
- **Chọn "File"** → chọn file PDF/DOCX test
- **Tóm tắt** → hiện kết quả
- **Nói**: "Hỗ trợ PDF, DOCX, EPUB, TXT, Markdown, tối đa 10MB"

### 1:45–2:15 | Lịch sử & Tìm kiếm
- **Click "Lịch sử"** → hiển thị 3 bản ghi (từ seed_demo + vừa tạo)
- **Nhập từ khóa** "Django" → lọc real-time
- **Nói**: "Tìm kiếm full-text (PostgreSQL) hoặc fallback icontains (SQLite/MySQL)"

### 2:15–2:45 | Xuất file & Chia sẻ
- **Click một bản ghi** → xem chi tiết
- **Nhấn "Xuất Markdown"** → download .md
- **Nhấn "Xuất DOCX"** → download .docx
- **Nhấn "Xuất PDF"** → download .pdf
- **Nhấn "Chia sẻ"** → chọn 7 ngày → copy link → mở tab ẩn danh → dán link → xem công khai
- **Nói**: "Link chia sẻ có thời hạn, ký HMAC, không cần đăng nhập"

### 2:45–3:00 | Webhook & Kết thúc
- **Vào "Webhook"** → thêm URL `https://webhook.site/xxx`, chọn event "summary.completed"
- **Nhấn "Test"** → thấy "Test webhook sent successfully"
- **Mở webhook.site** → thấy payload JSON
- **Nói**: "Webhook có outbox transactional, retry exponential backoff, vô hiệu sau 10 lỗi"
- **Kết**: "SummarEase - tóm tắt thông minh, sẵn sàng triển khai"

---

## Tips quay đẹp
- **Full HD 1080p**, 30fps
- **Zoom vào text** khi dán/paste (Ctrl+Scroll)
- **Highlight chuột** (cài đặt Windows > Mouse > Show location)
- **Ghi âm rõ ràng** (mic gần miệng, ít tiếng ồn)
- **Cắt bỏ loading chờ** (fast-forward 2-4x)
- **Thêm caption** tiếng Việt cho các bước chính

---

## File test sẵn có
```
# Văn bản (copy từ vn_dataset.json)
vn_01: Django framework
vn_02: TextRank algorithm
vn_03: AI ethics

# URL test
https://vnexpress.net/giao-duc/du-hoc-sinh-viet-nam-tang-manh-4721234.html

# File test (tự tạo hoặc download)
test.pdf, test.docx, test.epub, test.txt
```

---

## Upload video
- **YouTube** (unlisted) → link trong README
- **Google Drive** (backup) → chia sẻ cho GV
- **Caption tự động** YouTube → sửa lỗi → xuất .vtt