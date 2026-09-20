"""Webhook callbacks for summary completion notifications."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Summary
from .readers import _resolve_and_validate

logger = logging.getLogger(__name__)

# Retry configuration
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_DELAYS = [10, 60, 300]  # seconds: 10s, 1min, 5min
WEBHOOK_TIMEOUT = 15  # seconds
DELIVERY_MAX_ATTEMPTS = 5
DELIVERY_RETRY_DELAYS = [30, 120, 600, 1800]  # 30s, 2min, 10min, 30min


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

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="webhooks")
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=64, help_text="HMAC secret for signature verification")
    events = models.JSONField(
        default=list,
        help_text="List of events to subscribe to: ['summary.completed', 'summary.failed']",
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
        expected = hmac.new(self.secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class WebhookDelivery(models.Model):
    """Durable outbox row for delivering one event to one webhook endpoint."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Đang chờ"),
        (PROCESSING, "Đang gửi"),
        (DELIVERED, "Đã gửi"),
        (FAILED, "Gửi thất bại"),
    ]

    webhook = models.ForeignKey(
        WebhookRegistration, on_delete=models.CASCADE, related_name="deliveries"
    )
    summary = models.ForeignKey(
        Summary, on_delete=models.CASCADE, related_name="webhook_deliveries"
    )
    event = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["webhook", "summary", "event"], name="unique_webhook_summary_event"
            )
        ]
        indexes = [models.Index(fields=["status", "available_at"])]


def validate_webhook_url(url: str) -> None:
    """Reject non-HTTP(S), credential-bearing, or private-network destinations."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        _ = parsed.port  # Validate that an explicitly supplied port is numeric and in range.
    except ValueError as exc:
        raise ValueError("URL webhook không hợp lệ.") from exc

    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or (not settings.DEBUG and parsed.scheme != "https")
    ):
        raise ValueError("Webhook production phải dùng URL HTTPS hợp lệ.")

    try:
        _resolve_and_validate(host)
    except ValueError as exc:
        raise ValueError("Webhook phải trỏ tới địa chỉ máy chủ công khai.") from exc


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


def _canonical_payload(payload: dict) -> bytes:
    """Serialize a payload deterministically for signing and delivery."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def _sign_payload(payload: dict, secret: str) -> str:
    """Generate HMAC signature for payload."""
    payload_bytes = _canonical_payload(payload)
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _record_webhook_failure(webhook: WebhookRegistration) -> None:
    webhook.failure_count += 1
    if webhook.failure_count >= 10:
        webhook.is_active = False
        logger.error("Webhook disabled after repeated failures: id=%s", webhook.pk)
    webhook.save(update_fields=["failure_count", "is_active"])


def _deliver_webhook(
    webhook: WebhookRegistration,
    payload: WebhookPayload,
    *,
    max_retries: int = WEBHOOK_MAX_RETRIES,
    delivery_id: str = "",
) -> bool:
    """Deliver webhook with retries. Returns True if successful."""
    payload_dict = payload.to_dict()
    payload_bytes = _canonical_payload(payload_dict)
    signature = _sign_payload(payload_dict, webhook.secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": payload.event,
        "X-Webhook-Timestamp": str(payload.timestamp),
        "User-Agent": "SummarEase-Webhook/1.0",
    }
    if delivery_id:
        headers["X-Webhook-Delivery"] = delivery_id

    for attempt in range(max_retries):
        try:
            validate_webhook_url(webhook.url)
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    webhook.url,
                    data=payload_bytes,
                    headers=headers,
                    timeout=WEBHOOK_TIMEOUT,
                    allow_redirects=False,
                )
        except ValueError as exc:
            logger.warning("Webhook URL rejected during delivery: id=%s reason=%s", webhook.pk, exc)
            _record_webhook_failure(webhook)
            return False
        except requests.RequestException as exc:
            logger.warning(
                "Webhook request failed: id=%s attempt=%s error=%s",
                webhook.pk,
                attempt + 1,
                type(exc).__name__,
            )
        else:
            if 200 <= response.status_code < 300:
                webhook.failure_count = 0
                webhook.last_triggered = timezone.now()
                webhook.save(update_fields=["failure_count", "last_triggered"])
                logger.info("Webhook delivered: id=%s event=%s", webhook.pk, payload.event)
                return True
            logger.warning("Webhook failed: id=%s status=%s", webhook.pk, response.status_code)

        if attempt < max_retries - 1:
            time.sleep(WEBHOOK_RETRY_DELAYS[attempt])

    # All retries failed
    _record_webhook_failure(webhook)
    return False


@receiver(post_save, sender=Summary)
def summary_webhook_signal(sender, instance: Summary, created: bool, **kwargs):
    """Write webhook outbox rows in the summary transaction, then enqueue after commit."""
    if not created:
        return

    delivery_ids = []
    for webhook in WebhookRegistration.objects.filter(user_id=instance.user_id, is_active=True):
        if "summary.completed" not in (webhook.events or []):
            continue
        delivery, was_created = WebhookDelivery.objects.get_or_create(
            webhook=webhook,
            summary=instance,
            event="summary.completed",
        )
        if was_created:
            delivery_ids.append(delivery.pk)

    if not delivery_ids:
        return

    def enqueue_deliveries() -> None:
        from .tasks import dispatch_webhook_delivery

        for delivery_id in delivery_ids:
            if settings.DEBUG:
                dispatch_webhook_delivery(delivery_id)
                continue
            try:
                dispatch_webhook_delivery.delay(delivery_id)
            except Exception:  # noqa: BLE001
                # The outbox row stays pending and will be picked up by the periodic sweeper.
                logger.exception("Could not queue webhook delivery id=%s", delivery_id)

    transaction.on_commit(enqueue_deliveries)

    # Failure webhooks are triggered from the summarization task itself.
