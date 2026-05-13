from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=[("text", "Text"), ("file", "File"), ("url", "URL")], max_length=20)),
                ("title", models.CharField(max_length=255)),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("uploaded_file", models.FileField(blank=True, upload_to="documents/")),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Summary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("method", models.CharField(choices=[("textrank", "TextRank"), ("gemini", "Gemini")], default="textrank", max_length=20)),
                ("language", models.CharField(default="english", max_length=20)),
                ("ratio", models.FloatField(default=0.2)),
                ("summary_text", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="summaries", to="summaries.document")),
                ("tags", models.ManyToManyField(blank=True, related_name="summaries", to="summaries.tag")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="summaries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SummarySentence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sentence_text", models.TextField()),
                ("sentence_index", models.PositiveIntegerField(default=0)),
                ("is_highlighted", models.BooleanField(default=True)),
                ("summary", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sentences", to="summaries.summary")),
            ],
            options={"ordering": ["sentence_index"]},
        ),
        migrations.CreateModel(
            name="Evaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("evaluator_type", models.CharField(choices=[("ai", "AI"), ("human", "Human")], default="human", max_length=10)),
                ("clarity_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("coverage_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("fluency_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("comments", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("summary", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evaluations", to="summaries.summary")),
            ],
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("admin", "Admin"), ("user", "User")], default="user", max_length=20)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="UserSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("default_summary_ratio", models.FloatField(default=0.2)),
                ("language_preference", models.CharField(default="auto", max_length=20)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="setting", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
