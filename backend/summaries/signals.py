"""Post-save signals for SummarEase."""

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import (
    HAS_POSTGRES_SEARCH,
    Document,
    Summary,
    UserProfile,
    UserSetting,
    _cleanup_uploaded_file,
)


@receiver(pre_delete, sender=Document)
def cleanup_document_upload(sender, instance, **kwargs):
    if instance.uploaded_file:
        transaction.on_commit(lambda: _cleanup_uploaded_file(instance.uploaded_file))


if HAS_POSTGRES_SEARCH:
    from django.contrib.postgres.search import SearchVector


@receiver(post_save, sender=User)
def ensure_user_defaults(sender, instance, created, **kwargs):
    """Create UserProfile and UserSetting on user creation."""
    if created:
        role = UserProfile.ROLE_ADMIN if instance.is_superuser else UserProfile.ROLE_USER
        UserProfile.objects.get_or_create(user=instance, defaults={"role": role})
        UserSetting.objects.get_or_create(user=instance)

    # Sync superuser → admin role
    if instance.is_superuser:
        UserProfile.objects.filter(user=instance).exclude(role=UserProfile.ROLE_ADMIN).update(
            role=UserProfile.ROLE_ADMIN
        )


if HAS_POSTGRES_SEARCH:

    @receiver(post_save, sender=Summary)
    def update_summary_search_vector(sender, instance, **kwargs):
        """Update search vector on summary save (PostgreSQL only)."""
        # Use update() to avoid triggering this signal again
        Summary.objects.filter(pk=instance.pk).update(
            search_vector=(
                SearchVector("title", weight="A", config="simple")
                + SearchVector("summary_text", weight="B", config="simple")
            )
        )
