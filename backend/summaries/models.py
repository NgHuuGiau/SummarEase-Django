from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


# Kiểu trường full-text search tùy database. Quyết định đến từ settings
# (USE_POSTGRES_SEARCH) chứ không phải connection.vendor: đọc connection lúc import
# khiến schema phụ thuộc database nào được mở trước.
def _load_search_vector_field() -> type[models.Field] | None:
    try:
        from django.contrib.postgres.search import SearchVectorField
    except ImportError:
        return None
    return SearchVectorField


HAS_POSTGRES_SEARCH = getattr(settings, "USE_POSTGRES_SEARCH", False)
_search_vector_field = _load_search_vector_field() if HAS_POSTGRES_SEARCH else None
HAS_POSTGRES_SEARCH = HAS_POSTGRES_SEARCH and _search_vector_field is not None


def _cleanup_uploaded_file(file_path: str) -> None:
    from pathlib import Path

    if not file_path:
        return
    media_root = Path(settings.MEDIA_ROOT).resolve()
    full_path = (media_root / file_path).resolve()
    if not full_path.is_relative_to(media_root):
        return
    try:
        if full_path.exists():
            full_path.unlink()
    except OSError:
        pass


class UserProfile(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_USER = "user"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Quản trị viên"),
        (ROLE_USER, "Người dùng"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        help_text="Metadata cũ; quyền truy cập dùng is_staff/is_superuser của Django.",
    )

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class UserSetting(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="setting")
    default_summary_ratio = models.FloatField(default=0.2)
    language_preference = models.CharField(
        max_length=20,
        default="auto",
        help_text="Chưa áp dụng; ngôn ngữ hiện được nhận diện từ nội dung.",
    )
    gemini_api_key = models.CharField(
        max_length=255, blank=True, default="", help_text="API key Gemini cá nhân (nếu có)"
    )

    class Meta:
        verbose_name = "Cài đặt"
        verbose_name_plural = "Cài đặt"

    def __str__(self) -> str:
        return f"Cài đặt của {self.user.username}"


class Document(models.Model):
    SOURCE_TEXT = "text"
    SOURCE_FILE = "file"
    SOURCE_URL = "url"
    SOURCE_CHOICES = (
        (SOURCE_TEXT, "Văn bản"),
        (SOURCE_FILE, "Tệp"),
        (SOURCE_URL, "URL"),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="documents", db_index=True
    )
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255, blank=True)
    uploaded_file = models.CharField(max_length=500, blank=True, default="")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Summary(models.Model):
    METHOD_TEXTRANK = "textrank"
    METHOD_GEMINI = "gemini"
    METHOD_CHOICES = (
        (METHOD_TEXTRANK, "TextRank"),
        (METHOD_GEMINI, "Gemini"),
    )

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="summaries", db_index=True
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="summaries", db_index=True
    )
    title = models.CharField(max_length=255)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_TEXTRANK)
    language = models.CharField(max_length=20, default="auto")
    ratio = models.FloatField(default=0.2)
    summary_text = models.TextField()
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="summaries")

    # Full-text search vector (PostgreSQL uses SearchVectorField, SQLite uses TextField)
    if HAS_POSTGRES_SEARCH and _search_vector_field is not None:
        search_vector = _search_vector_field(null=True, editable=False)
    else:
        # SQLite fallback: simple text field for compatibility
        search_vector = models.TextField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]
        if HAS_POSTGRES_SEARCH and _search_vector_field is not None:
            indexes.append(models.Index(fields=["search_vector"]))

    def __str__(self) -> str:
        return self.title

    @classmethod
    def search(cls, user, query: str, language: str = "vietnamese"):
        """Full-text search summaries for a user (PostgreSQL only)."""
        summaries = cls.objects.all()
        if user is not None:
            summaries = summaries.filter(user=user)
        if not HAS_POSTGRES_SEARCH:
            # SQLite fallback: simple icontains search
            return summaries.filter(
                models.Q(title__icontains=query) | models.Q(summary_text__icontains=query)
            ).order_by("-created_at")

        from django.contrib.postgres.search import SearchQuery, SearchRank

        search_query = SearchQuery(query, config=language)
        return (
            summaries.annotate(rank=SearchRank("search_vector", search_query))
            .filter(rank__gte=0.1)
            .order_by("-rank", "-created_at")
        )


class SummarySentence(models.Model):
    summary = models.ForeignKey(
        Summary, on_delete=models.CASCADE, related_name="sentences", db_index=True
    )
    sentence_text = models.TextField()
    sentence_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sentence_index"]
