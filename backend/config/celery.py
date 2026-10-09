"""Celery app configuration for SummarEase."""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("summarease")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["summaries"])
