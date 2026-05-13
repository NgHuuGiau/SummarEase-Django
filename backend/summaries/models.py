from django.contrib.auth.models import User
from django.db import models


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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    title = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255, blank=True)
    uploaded_file = models.FileField(upload_to="documents/", blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="summaries")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="summaries")
    title = models.CharField(max_length=255)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_TEXTRANK)
    language = models.CharField(max_length=20, default="english")
    ratio = models.FloatField(default=0.2)
    summary_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="summaries")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class SummarySentence(models.Model):
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name="sentences")
    sentence_text = models.TextField()
    sentence_index = models.PositiveIntegerField(default=0)
    is_highlighted = models.BooleanField(default=True)

    class Meta:
        ordering = ["sentence_index"]


class Evaluation(models.Model):
    EVALUATOR_AI = "ai"
    EVALUATOR_HUMAN = "human"
    EVALUATOR_CHOICES = (
        (EVALUATOR_AI, "AI"),
        (EVALUATOR_HUMAN, "Người"),
    )

    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name="evaluations")
    evaluator_type = models.CharField(max_length=10, choices=EVALUATOR_CHOICES, default=EVALUATOR_HUMAN)
    clarity_score = models.PositiveSmallIntegerField(null=True, blank=True)
    coverage_score = models.PositiveSmallIntegerField(null=True, blank=True)
    fluency_score = models.PositiveSmallIntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def overall_score(self) -> float | None:
        scores = [self.clarity_score, self.coverage_score, self.fluency_score]
        values = [score for score in scores if score is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 2)
