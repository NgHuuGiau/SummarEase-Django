"""Quản lý: tạo dữ liệu demo cho buổi trình diễn."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from summaries.models import Document, Summary, Tag, UserProfile, UserSetting

DEMO_DOCS = [
    {
        "title": "Django - Framework Web Python",
        "source_type": "text",
        "source_name": "Wiki",
        "content": (
            "Django là một khung làm việc web cấp cao viết bằng Python, khuyến khích "
            "phát triển nhanh chóng và thiết kế sạch sẽ, thực tế. Được xây dựng bởi "
            "các nhà phát triển có kinh nghiệm, Django lo gánh nặng của việc phát triển "
            "web để bạn có thể tập trung vào viết ứng dụng của mình mà không cần phát "
            "minh lại bánh xe. Nó miễn phí và nguồn mở. Django tuân theo mô hình MVT "
            "(Model-View-Template) và cung cấp sẵn admin, authentication, ORM, forms, "
            "caching, internationalization. Cộng đồng lớn, tài liệu đầy đủ, bảo mật tốt "
            "(CSRF, XSS, SQL injection protection). Phiên bản mới nhất Django 5.2 "
            "hỗ trợ Python 3.10-3.13, async views, JSONField, improved caching."
        ),
    },
    {
        "title": "TextRank - Thuật Toán Tóm Tắt Dựa Trên Đồ Thị",
        "source_type": "text",
        "source_name": "NLP Paper",
        "content": (
            "TextRank là thuật toán xếp hạng dựa trên đồ thị dùng cho tóm tắt văn bản "
            "và trích xuất từ khóa. Nó xây dựng đồ thị các câu, trong đó mỗi câu là một "
            "nút, và cạnh giữa các nút đại diện cho độ tương đồng ngữ nghĩa. Thuật toán "
            "sau đó áp dụng PageRank (dùng trong Google Search) để tính điểm quan trọng "
            "cho mỗi câu. Các câu có điểm cao nhất được chọn để tạo bản tóm tắt. Ưu điểm: "
            "không cần dữ liệu huấn luyện, chạy nhanh, không phụ thuộc ngôn ngữ (chỉ cần "
            "stop words), giải thích được. Nhược điểm: chỉ trích xuất câu gốc "
            "(extractive), không viết lại (abstractive), chất lượng phụ thuộc vào cách "
            "chia câu và stop words. So với BART/T5/GPT (abstractive), TextRank nhẹ hơn "
            "nhiều, chạy offline."
        ),
    },
    {
        "title": "Container Hóa Ứng Dụng Với Docker",
        "source_type": "text",
        "source_name": "DevOps Guide",
        "content": (
            "Docker là nền tảng container hóa ứng dụng, đóng gói mã nguồn và tất cả "
            "phụ thuộc vào một image nhẹ, chạy giống hệt nhau trên mọi môi trường "
            "(laptop, server, CI/CD). Khác với máy ảo: container chia sẻ kernel của "
            "host, khởi động trong vài giây, nhẹ hơn hàng trăm MB. Dockerfile định "
            "nghĩa image theo lớp (layer), tận dụng cache để build nhanh. "
            "docker-compose điều phối nhiều container (web, db, redis) bằng file "
            "YAML đơn giản. Dùng cho: phát triển nhất quán, CI/CD pipeline, "
            "microservices, triển khai production. Kubernetes (K8s) điều phối "
            "container ở quy mô lớn: auto-scaling, self-healing, rolling update."
        ),
    },
]


DEMO_TAGS = [
    "django",
    "python",
    "web",
    "framework",
    "textrank",
    "nlp",
    "tóm tắt",
    "thuật toán",
    "docker",
    "container",
    "devops",
    "kubernetes",
]


class Command(BaseCommand):
    help = "Tạo dữ liệu demo (user, tài liệu, tóm tắt, tag) cho buổi trình diễn"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="demo",
            help="Tên tài khoản demo (mặc định: demo)",
        )
        parser.add_argument(
            "--password",
            default="demo123456",
            help="Mật khẩu (mặc định: demo123456)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Xoá dữ liệu demo cũ trước khi tạo mới",
        )

    def handle(self, *args, **opts):
        username = opts["username"]
        password = opts["password"]

        if opts["clear"]:
            User.objects.filter(username=username).delete()
            self.stdout.write(f"Đã xoá user demo cũ: {username}")

        # Tạo user demo
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            self.stdout.write(f"User '{username}' đã tồn tại")
        else:
            user = User.objects.create_user(username=username, password=password)
            self.stdout.write(f"Đã tạo user demo: {username} / {password}")

        # UserProfile & UserSetting
        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={"role": UserProfile.ROLE_USER}
        )
        setting, _ = UserSetting.objects.get_or_create(user=user)

        # Tạo tags
        tag_objs = {}
        for tag_name in DEMO_TAGS:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            tag_objs[tag_name] = tag

        # Tạo documents & summaries
        from summaries.nlp import textrank_summarize

        created_docs = 0
        created_summaries = 0

        for doc_data in DEMO_DOCS:
            # Kiểm tra trùng lặp
            if Document.objects.filter(user=user, title=doc_data["title"]).exists():
                self.stdout.write(f"  Bỏ qua (đã có): {doc_data['title']}")
                continue

            doc = Document.objects.create(
                user=user,
                source_type=doc_data["source_type"],
                title=doc_data["title"],
                source_name=doc_data["source_name"],
                content=doc_data["content"],
            )
            created_docs += 1

            # Tóm tắt bằng TextRank
            result = textrank_summarize(doc.content, ratio=0.3, language="vietnamese")
            summary = Summary.objects.create(
                document=doc,
                user=user,
                title=doc_data["title"],
                method="textrank",
                language="vietnamese",
                ratio=0.3,
                summary_text=result["summary"],
            )
            # Gán tags
            for kw in result["keywords"]:
                if kw in tag_objs:
                    summary.tags.add(tag_objs[kw])
            # Tạo câu tóm tắt
            from summaries.nlp_utils import split_sentences

            for idx, sent in enumerate(split_sentences(result["summary"])):
                if sent.strip():
                    from summaries.models import SummarySentence

                    SummarySentence.objects.create(
                        summary=summary, sentence_text=sent.strip(), sentence_index=idx
                    )
            created_summaries += 1
            self.stdout.write(f"  Đã tạo: {doc.title} ({len(result['summary'])} ký tự)")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nHoàn tất! User: {username}/{password} | "
                f"Tài liệu: {created_docs} | Tóm tắt: {created_summaries} | Tags: {len(DEMO_TAGS)}"
            )
        )
        self.stdout.write("Đăng nhập tại /login/ để xem lịch sử, tìm kiếm, xuất file, chia sẻ.")
