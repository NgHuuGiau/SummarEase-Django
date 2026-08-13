from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


def _cleanup_uploaded_file(file_path: str) -> None:
    if not file_path:
        return
    full_path = Path(settings.MEDIA_ROOT) / file_path
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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class UserSetting(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="setting")
    default_summary_ratio = models.FloatField(default=0.2)
    language_preference = models.CharField(max_length=20, default="auto")
    gemini_api_key = models.CharField(max_length=255, blank=True, default="", help_text="API key Gemini cá nhân (nếu có)")

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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents", db_index=True)
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

    def delete(self, *args, **kwargs):
        _cleanup_uploaded_file(self.uploaded_file)
        super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class Summary(models.Model):
    METHOD_TEXTRANK = "textrank"
    METHOD_GEMINI = "gemini"
    METHOD_CHOICES = (
        (METHOD_TEXTRANK, "TextRank"),
        (METHOD_GEMINI, "Gemini"),
    )

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="summaries", db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="summaries", db_index=True)
    title = models.CharField(max_length=255)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_TEXTRANK)
    language = models.CharField(max_length=20, default="english")
    ratio = models.FloatField(default=0.2)
    summary_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="summaries")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.title


class SummarySentence(models.Model):
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name="sentences", db_index=True)
    sentence_text = models.TextField()
    sentence_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sentence_index"]
