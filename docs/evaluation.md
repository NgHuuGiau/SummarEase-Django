# Quy trình đánh giá chất lượng tóm tắt

## Mục tiêu

Đánh giá TextRank và Gemini trên cùng văn bản nguồn, cùng bản tham chiếu và cùng tỷ lệ tóm tắt. Baseline “câu đầu” giúp kiểm tra liệu phương pháp có thực sự tốt hơn cách chọn câu đơn giản hay không. Không xem ROUGE là bằng chứng duy nhất về chất lượng.

## Chạy lại benchmark

Từ thư mục gốc dự án:

```powershell
python manage.py evaluate --method all --ratio 0.3 --output results/evaluate.json
python manage.py evaluate --method textrank --ratio 0.3 --output results/textrank.json
python manage.py evaluate --method gemini --ratio 0.3 --output results/gemini.json
```

Lệnh `all` chỉ chạy TextRank và baseline, không gọi dịch vụ ngoài. Để đánh giá Gemini, đặt `GEMINI_API_KEY` trong môi trường trước khi chạy; không truyền key qua đối số dòng lệnh, không đưa key vào dataset hay commit file chứa key. Mỗi lệnh Gemini gửi một yêu cầu cho mỗi mẫu thành công/thất bại và có thể phát sinh phí.

JSON đầu ra lưu phương pháp, tỷ lệ, đường dẫn dataset, số mẫu, và kết quả từng ID: reference, prediction, ROUGE-1/2/L F1, độ nén, thời gian, trạng thái lỗi. Trung bình chỉ tính các mẫu thành công; báo cáo cũng nêu riêng số thành công/thất bại. So sánh từng mẫu theo ID, không so hai danh sách đã lọc lỗi theo vị trí.

## Dataset hiện tại và hướng mở rộng

`backend/summaries/eval/vn_dataset.json` có 15 mẫu tiếng Việt. Dùng nó để kiểm tra lệnh và làm pilot, không đủ lớn hoặc đa dạng để đại diện cho mọi loại văn bản. Trước khi lấy kết quả làm kết luận đồ án:

1. Mở rộng lên khoảng 100–200 văn bản thuộc nhiều miền phù hợp với người dùng mục tiêu (ví dụ giáo dục, tin tức, công nghệ, hành chính); ghi rõ nguồn và tiêu chí chọn mẫu.
2. Viết reference độc lập sau khi đọc văn bản nguồn, không lấy output của TextRank/Gemini làm reference. Ghi người tạo, ngày tạo và hướng dẫn độ dài.
3. Có người thứ hai rà soát reference để sửa sai nội dung; loại dữ liệu có bản quyền/PII nếu chưa có quyền sử dụng.
4. Giữ cố định phiên bản dataset và hash/commit của benchmark cho mỗi lần chạy. Không thay nội dung reference giữa các phương pháp.

## Đo chất lượng với người đánh giá

ROUGE dựa trên độ trùng từ nên có thể đánh giá thấp cách diễn đạt lại bằng tiếng Việt, và không phát hiện đầy đủ thông tin bịa hoặc sai. Hãy bổ sung đánh giá thủ công mù: ẩn tên phương pháp, xáo trộn thứ tự output và nhờ ít nhất hai người chấm mỗi output trên thang 1–5 theo ba tiêu chí:

| Tiêu chí | Câu hỏi khi chấm |
|---|---|
| Độ bao phủ | Các ý quan trọng trong nguồn có được giữ lại không? |
| Tính trung thực | Có ý nào sai, bịa hoặc trái với nguồn không? |
| Khả năng đọc | Bản tóm tắt có mạch lạc, rõ nghĩa, dễ đọc không? |

Báo cáo số người chấm, cách xử lý bất đồng và điểm trung bình theo tiêu chí/phương pháp. Nếu có điều kiện, đo mức đồng thuận giữa người chấm (weighted Cohen’s kappa cho hai người). Chỉ thu thập phản hồi có đồng thuận và không lưu thông tin nhận diện không cần thiết.

## Cách trình bày kết quả

- Báo cáo ROUGE-1/2/L F1, độ nén và thời gian trung bình; với Gemini ghi rõ model, ngày chạy và điều kiện mạng.
- So sánh trên cùng các ID và nêu số mẫu lỗi; không bỏ các lỗi API khỏi phần mô tả kết quả.
- Không tuyên bố một phương pháp “tốt hơn” chỉ từ một chỉ số ROUGE hoặc 15 mẫu pilot.
- Nêu giới hạn: độ bao phủ dataset, chủ quan của reference/chấm tay, biến động API và chênh lệch giữa tiếng Việt tách theo âm tiết với tokenization ROUGE.
