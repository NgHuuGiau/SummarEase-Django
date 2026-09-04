from django.apps import AppConfig


class SummariesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "summaries"

    def ready(self):
        import summaries.checks  # noqa: F401
        import summaries.signals  # noqa: F401
