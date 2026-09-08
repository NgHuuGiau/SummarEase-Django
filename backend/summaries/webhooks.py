"""Webhook callbacks for summary completion notifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Summary

logger = logging.getLogger(__name__)

# Retry configuration
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_DELAYS = [10, 60, 300]  # seconds: 10s, 1min, 5min
WEBHOOK_TIMEOUT = 15  # seconds


@dataclass
class WebhookPayload:
    """Structured webhook payload for summary completion."""
    event: str  # "summary.completed" | "summary.failed"
    summary_id: int
    title: str
    method: str
    language: str
    ratio: float
    summary_text: str
    keywords: list[str]
    source_type: str
    source_name: str
    created_at: str  # ISO format
    history_url: str
    timestamp: int  # Unix timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "summary_id": self.summary_id,
            "title": self.title,
            "method": self.method,
            "language": self.language,
            "ratio": self.ratio,
            "summary_text": self.summary_text,
            "keywords": self.keywords,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "created_at": self.created_at,
            "history_url": self.history_url,
            "timestamp": self.timestamp,
        }


class WebhookRegistration(models.Model):
    """User-registered webhook endpoints."""
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name="webhooks"
    )
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=64, help_text="HMAC secret for signature verification")
    events = models.JSONField(
        default=list,
        help_text="List of events to subscribe to: ['summary.completed', 'summary.failed']"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.url}"

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC signature from webhook delivery."""
        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


def _build_webhook_payload(summary: Summary, event: str) -> WebhookPayload:
    """Build webhook payload from summary."""
    return WebhookPayload(
        event=event,
        summary_id=summary.id,
        title=summary.title,
        method=summary.method,
        language=summary.language,
        ratio=summary.ratio,
        summary_text=summary.summary_text,
        keywords=list(summary.tags.values_list("name", flat=True)),
        source_type=summary.document.source_type,
        source_name=summary.document.source_name,
        created_at=summary.created_at.isoformat(),
        history_url=f"/history/{summary.id}/",
        timestamp=int(time.time()),
    )


def _sign_payload(payload: dict, secret: str) -> str:
    """Generate HMAC signature for payload."""
    payload_bytes = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _deliver_webhook(webhook: WebhookRegistration, payload: WebhookPayload) -> bool:
    """Deliver webhook with retries. Returns True if successful."""
    payload_dict = payload.to_dict()
    payload_bytes = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False).encode()
    signature = _sign_payload(payload_dict, webhook.secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": payload.event,
        "X-Webhook-Timestamp": str(payload.timestamp),
        "User-Agent": "SummarEase-Webhook/1.0",
    }

    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            response = requests.post(
                webhook.url,
                data=payload_bytes,
                headers=headers,
                timeout=WEBHOOK_TIMEOUT,
            )
            if 200 <= response.status_code < 300:
                webhook.failure_count = 0
                webhook.last_triggered = time.time()
                webhook.save(update_fields=["failure_count", "last_triggered"])
                logger.info(f"Webhook delivered: {webhook.url} (event: {payload.event})")
                return True
            else:
                logger.warning(f"Webhook failed ({response.status_code}): {webhook.url}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Webhook error (attempt {attempt + 1}): {webhook.url} - {exc}")

        if attempt < WEBHOOK_MAX_RETRIES - 1:
            time.sleep(WEBHOOK_RETRY_DELAYS[attempt])

    # All retries failed
    webhook.failure_count += 1
    if webhook.failure_count >= 10:
        webhook.is_active = False
        logger.error(f"Webhook disabled due to repeated failures: {webhook.url}")
    webhook.save(update_fields=["failure_count", "is_active"])
    return False


def trigger_webhooks(user, summary: Summary, event: str) -> None:
    """Trigger all active webhooks for a user for the given event."""
    from django.db import connection
    
    # SQLite doesn't support __contains on JSONField, use raw SQL for cross-db compatibility
    if connection.vendor == 'sqlite':
        webhooks = WebhookRegistration.objects.filter(user=user, is_active=True)
        webhooks = [w for w in webhooks if event in (w.events or [])]
    else:
        webhooks = WebhookRegistration.objects.filter(
            user=user, is_active=True, events__contains=[event]
        )
    
    if not webhooks:
        return

    payload = _build_webhook_payload(summary, event)

    for webhook in webhooks:
        # Use cache to prevent duplicate triggers within 1 second
        cache_key = f"webhook:{webhook.id}:{summary.id}:{event}"
        if cache.get(cache_key):
            continue
        cache.set(cache_key, "1", 1)

        # Deliver asynchronously (in production, use Celery task)
        _deliver_webhook(webhook, payload)


@receiver(post_save, sender=Summary)
def summary_webhook_signal(sender, instance: Summary, created: bool, **kwargs):
    """Trigger webhooks on summary creation."""
    if not created:
        return

    # Trigger success webhook
    trigger_webhooks(instance.user, instance, "summary.completed")

    # Note: Failure webhooks are triggered from the task itself