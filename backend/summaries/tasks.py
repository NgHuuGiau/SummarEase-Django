"""Celery tasks for async summarization."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import InterfaceError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from .metrics import summary_created, summary_failed
from .models import _cleanup_uploaded_file
from .nlp import TextTooLargeError, gemini_summarize, textrank_summarize
from .nlp_utils import detect_language
from .persistence import persist_summary
from .readers import TransientNetworkError, extract_text

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_FILE_SIZE = 10 * 1024 * 1024


@shared_task
def dispatch_webhook_delivery(delivery_id: int) -> None:
    """Attempt one durable webhook delivery; retries are scheduled without blocking a worker."""
    from .webhooks import (
        DELIVERY_MAX_ATTEMPTS,
        DELIVERY_RETRY_DELAYS,
        WebhookDelivery,
        _build_webhook_payload,
        _deliver_webhook,
    )

    now = timezone.now()
    claimed = WebhookDelivery.objects.filter(
        pk=delivery_id,
        status=WebhookDelivery.PENDING,
        available_at__lte=now,
    ).update(status=WebhookDelivery.PROCESSING, locked_at=now)
    if not claimed:
        return

    delivery = WebhookDelivery.objects.select_related(
        "webhook", "summary", "summary__document"
    ).get(pk=delivery_id)
    webhook = delivery.webhook
    if not webhook.is_active:
        delivery.status = WebhookDelivery.FAILED
        delivery.locked_at = None
        delivery.save(update_fields=["status", "locked_at"])
        return

    summary = delivery.summary
    success = _deliver_webhook(
        webhook,
        _build_webhook_payload(summary, delivery.event),
        max_retries=1,
        delivery_id=str(delivery.pk),
    )
    delivery.locked_at = None
    if success:
        delivery.status = WebhookDelivery.DELIVERED
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "locked_at", "delivered_at"])
        return

    delivery.attempt_count += 1
    if delivery.attempt_count >= DELIVERY_MAX_ATTEMPTS:
        delivery.status = WebhookDelivery.FAILED
        delay = 0
    else:
        delivery.status = WebhookDelivery.PENDING
        delay = DELIVERY_RETRY_DELAYS[delivery.attempt_count - 1]
        delivery.available_at = timezone.now() + timedelta(seconds=delay)
    delivery.save(update_fields=["status", "attempt_count", "available_at", "locked_at"])


@shared_task
def enqueue_pending_webhook_deliveries() -> int:
    """Recover stale claims and enqueue due outbox rows in bounded batches."""
    from .webhooks import DELIVERY_MAX_ATTEMPTS, WebhookDelivery

    now = timezone.now()
    stale = WebhookDelivery.objects.filter(
        status=WebhookDelivery.PROCESSING,
        locked_at__lt=now - timedelta(minutes=15),
    )
    stale.filter(attempt_count__gte=DELIVERY_MAX_ATTEMPTS - 1).update(
        status=WebhookDelivery.FAILED,
        attempt_count=F("attempt_count") + 1,
        locked_at=None,
    )
    stale.filter(attempt_count__lt=DELIVERY_MAX_ATTEMPTS - 1).update(
        status=WebhookDelivery.PENDING,
        attempt_count=F("attempt_count") + 1,
        locked_at=None,
        available_at=now,
    )

    delivery_ids = list(
        WebhookDelivery.objects.filter(
            status=WebhookDelivery.PENDING,
            available_at__lte=now,
        )
        .order_by("available_at", "pk")
        .values_list("pk", flat=True)[:100]
    )
    enqueued = 0
    for delivery_id in delivery_ids:
        try:
            dispatch_webhook_delivery.delay(delivery_id)
            enqueued += 1
        except Exception:  # noqa: BLE001
            logger.exception("Could not enqueue pending webhook delivery id=%s", delivery_id)
            break
    return enqueued


def _schedule_file_cleanup(file_path: str) -> None:
    """Schedule file cleanup after transaction commits."""
    if file_path:
        transaction.on_commit(lambda: _cleanup_uploaded_file(file_path))


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_summary_task(
    self,
    user_id: int,
    source_type: str,
    method: str,
    ratio: float,
    text: str = "",
    source_url: str = "",
    file_path: str = "",
    user_api_key: str = "",
) -> dict:
    """Background task to process summarization request."""
    start_time = time.time()
    logger.info(
        "process_summary_task started: user=%d, source=%s, method=%s, ratio=%.2f",
        user_id,
        source_type,
        method,
        ratio,
    )

    stored_file_name = file_path
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _schedule_file_cleanup(stored_file_name)
        return {"ok": False, "message": "Người dùng không tồn tại."}
    except (InterfaceError, OperationalError) as exc:
        if self.request.retries < self.max_retries:
            logger.warning(
                "Temporary database error; retrying summary task: user=%d attempt=%d/%d",
                user_id,
                self.request.retries + 1,
                self.max_retries,
            )
            raise self.retry(exc=exc) from exc
        summary_failed.labels(method=method, error_type=type(exc).__name__).inc()
        logger.error("Summary task exhausted database retries: user=%d", user_id)
        _schedule_file_cleanup(stored_file_name)
        return {
            "ok": False,
            "message": "Dịch vụ dữ liệu tạm thời không khả dụng. Vui lòng thử lại sau.",
        }

    source_name = ""
    original_text = ""
    uploaded_file_path = ""

    try:
        if source_type == "text":
            original_text = text.strip()
            source_name = "Văn bản nhập tay"
        elif source_type == "url":
            source_name = source_url
            original_text = extract_text(source_name)
        elif source_type == "file" and file_path:
            source_name = Path(file_path).name
            uploaded_file_path = str(Path(settings.MEDIA_ROOT) / file_path)
            original_text = extract_text(Path(uploaded_file_path))
            stored_file_name = file_path
        else:
            return {"ok": False, "message": "Không có nội dung để tóm tắt."}

        if not original_text.strip():
            raise ValueError("Không thể trích xuất nội dung từ nguồn đã chọn.")

        language = detect_language(original_text)
        if method == "gemini":
            result = gemini_summarize(
                original_text, ratio=ratio, language=language, user_api_key=user_api_key
            )
        else:
            result = textrank_summarize(original_text, ratio=ratio, language=language)

        summary = persist_summary(
            user,
            source_type,
            source_name,
            original_text,
            method,
            ratio,
            result,
            uploaded_file=stored_file_name,
        )

        elapsed = time.time() - start_time
        summary_created.labels(method=method, source_type=source_type).inc()
        logger.info(
            "process_summary_task done: user=%d, summary_id=%d, elapsed=%.2fs",
            user_id,
            summary.id,
            elapsed,
        )

        return {
            "ok": True,
            "data": {
                "id": summary.id,
                "title": summary.title,
                "language": summary.language,
                "method": summary.method,
                "ratio": summary.ratio,
                "summary": result["summary"],
                "highlighted_summary": result["highlighted_summary"],
                "keywords": result["keywords"],
                "source_type": source_type,
                "source_name": source_name,
                "created_at": summary.created_at.strftime("%d/%m/%Y %H:%M"),
                "history_url": f"/history/{summary.id}/",
            },
        }

    except (
        InterfaceError,
        OperationalError,
        TransientNetworkError,
    ) as exc:
        if self.request.retries < self.max_retries:
            logger.warning(
                "Temporary dependency error; retrying summary task: user=%d attempt=%d/%d error=%s",
                user_id,
                self.request.retries + 1,
                self.max_retries,
                type(exc).__name__,
            )
            raise self.retry(exc=exc) from exc
        summary_failed.labels(method=method, error_type=type(exc).__name__).inc()
        logger.error(
            "Summary task exhausted transient retries: user=%d error=%s",
            user_id,
            type(exc).__name__,
        )
        _schedule_file_cleanup(stored_file_name)
        return {
            "ok": False,
            "message": "Dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau.",
        }
    except Exception as exc:  # noqa: BLE001
        summary_failed.labels(method=method, error_type=type(exc).__name__).inc()
        logger.exception("process_summary_task failed: user=%d", user_id)
        _schedule_file_cleanup(stored_file_name)
        message = (
            str(exc)
            if isinstance(exc, TextTooLargeError)
            else "Không thể xử lý yêu cầu. Vui lòng thử lại sau."
        )
        return {"ok": False, "message": message}
