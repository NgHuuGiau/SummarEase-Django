"""Django system checks cho cấu hình vận hành."""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_production_encryption_key(app_configs, **kwargs):
    """Cảnh báo khi chạy production mà không set API_ENCRYPTION_KEY riêng."""
    errors = []
    if not settings.DEBUG and not getattr(settings, "API_ENCRYPTION_KEY_EXPLICIT", False):
        errors.append(
            Warning(
                "API_ENCRYPTION_KEY không được set tường minh trong production; "
                "key hiện derive từ DJANGO_SECRET_KEY.",
                id="summaries.W001",
            )
        )
    return errors
