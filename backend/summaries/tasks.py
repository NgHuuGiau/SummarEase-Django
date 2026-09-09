"""Celery tasks for async summarization."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Document, Summary, SummarySentence, Tag, _cleanup_uploaded_file
from .nlp import gemini_summarize, textrank_summarize
from .nlp_utils import detect_language
from .readers import extract_text

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_FILE_SIZE = 10 * 1024 * 1024


def _schedule_file_cleanup(file_path: str) -> None:
    """Schedule file cleanup after transaction commits."""
    if file_path:
        transaction.on_commit(lambda: _cleanup_uploaded_file(file_path))


@shared_task(bind=True, max_retries=3, default_retry_delay=30, autoretry_for=(Exception,))
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
        user_id, source_type, method, ratio
    )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return {"ok": False, "message": "Người dùng không tồn tại."}

    source_name = ""
    original_text = ""
    stored_file_name = ""
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

        title = result["title"][:255]

        with transaction.atomic():
            document = Document.objects.create(
                user=user,
                source_type=source_type,
                title=title,
                source_name=source_name[:255],
                uploaded_file=stored_file_name,
                content=original_text,
            )
            summary = Summary.objects.create(
                document=document,
                user=user,
                title=title,
                method=method,
                language=result["language"],
                ratio=ratio,
                summary_text=result["summary"],
            )
            tag_names = list(dict.fromkeys(kw[:100] for kw in result["keywords"]))
            if tag_names:
                all_tags = []
                for name in tag_names:
                    tag, _ = Tag.objects.get_or_create(name=name)
                    all_tags.append(tag)
                summary.tags.add(*all_tags)
            SummarySentence.objects.bulk_create(
                [
                    SummarySentence(summary=summary, sentence_text=sentence, sentence_index=index)
                    for index, sentence in enumerate(result["sentences"], start=1)
                ]
            )

        elapsed = time.time() - start_time
        logger.info(
            "process_summary_task done: user=%d, summary_id=%d, elapsed=%.2fs",
            user_id, summary.id, elapsed
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

    except (OSError, ValueError, Exception) as exc:  # noqa: BLE001
        logger.exception("process_summary_task failed: user=%d, error=%s", user_id, exc)
        _schedule_file_cleanup(stored_file_name)
        return {"ok": False, "message": str(exc)}
