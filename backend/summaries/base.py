"""Chung cho các module kiểm thử của app summaries."""

from django.contrib.auth.models import User


class TestHelperMixin:
    def _create_user(self, username, password="secret123", is_superuser=False):
        if is_superuser:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = User.objects.create_user(username=username, password=password)
        return user
