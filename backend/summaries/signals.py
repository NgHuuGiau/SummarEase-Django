"""Post-save signals for SummarEase."""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile, UserSetting


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
