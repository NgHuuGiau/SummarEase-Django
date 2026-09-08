"""Batch summarization for multiple files/URLs."""

from __future__ import annotations

import logging
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from celery import group
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from .models import Document, Summary, SummarySentence, Tag, _cleanup_uploaded_file
from .nlp import gemini_summarize, textrank_summarize
from .nlp_utils import detect_language
from .readers import extract_text
from .signing import decrypt_value, encrypt_value
from .tasks import process_summary_task

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_BATCH_SIZE = 20
MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}


def create_batch_from_zip(user, zip_file, method: str, ratio: float, user_api_key: str = "") -> dict:
    """Process a ZIP file containing multiple documents."""
    if zip_file.size > MAX_ZIP_SIZE:
        return {"ok": False, "message": "File ZIP vượt quá 50MB."}

    results = []
    errors = []
    processed = 0

    try:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            # Validate all files first
            file_list = []
            for name in zip_ref.namelist():
                if name.endswith('/') or name.startswith('__MACOSX'):
                    continue
                ext = Path(name).suffix.lower()
                if ext not in ALLOWED_EXTS:
                    errors.append(f"{name}: định dạng không hỗ trợ ({ext})")
                    continue
                file_list.append(name)

            if not file_list:
                return {"ok": False, "message": "Không có tệp hợp lệ trong ZIP.", "errors": errors}

            if len(file_list) > MAX_BATCH_SIZE:
                return {"ok": False, "message": f"ZIP chứa quá nhiều tệp (tối đa {MAX_BATCH_SIZE}).", "errors": errors}

            # Extract and process each file
            temp_dir = Path(settings.MEDIA_ROOT) / "batch_uploads" / uuid4().hex
            temp_dir.mkdir(parents=True, exist_ok=True)

            for name in file_list:
                try:
                    zip_ref.extract(name, temp_dir)
                    file_path = temp_dir / name

                    # Check file size
                    if file_path.stat().st_size > 10 * 1024 * 1024:
                        errors.append(f"{name}: vượt quá 10MB")
                        continue

                    # Extract text
                    original_text = extract_text(file_path)
                    if not original_text.strip():
                        errors.append(f"{name}: không trích xuất được nội dung")
                        continue

                    # Create summary using existing task (synchronously for batch)
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
                            source_type="file",
                            title=title,
                            source_name=name[:255],
                            uploaded_file=str(file_path.relative_to(settings.MEDIA_ROOT)),
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
                            for tn in tag_names:
                                tag, _ = Tag.objects.get_or_create(name=tn)
                                all_tags.append(tag)
                            summary.tags.add(*all_tags)
                        SummarySentence.objects.bulk_create(
                            [
                                SummarySentence(summary=summary, sentence_text=s, sentence_index=i)
                                for i, s in enumerate(result["sentences"], 1)
                            ]
                        )

                    results.append({
                        "id": summary.id,
                        "title": summary.title,
                        "file_name": name,
                        "method": method,
                        "language": result["language"],
                        "ratio": ratio,
                        "summary": result["summary"],
                        "keywords": result["keywords"],
                    })
                    processed += 1

                except Exception as exc:  # noqa: BLE001
                    logger.exception("Batch item failed: %s", name)
                    errors.append(f"{name}: {str(exc)}")

            # Cleanup temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

            return {
                "ok": True,
                "processed": processed,
                "total": len(file_list),
                "results": results,
                "errors": errors,
            }

    except zipfile.BadZipFile:
        return {"ok": False, "message": "File ZIP không hợp lệ hoặc bị hỏng."}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Batch processing failed")
        return {"ok": False, "message": f"Lỗi xử lý batch: {str(exc)}", "errors": errors}


def create_batch_from_urls(user, urls: list, method: str, ratio: float, user_api_key: str = "") -> dict:
    """Process multiple URLs in batch."""
    if len(urls) > MAX_BATCH_SIZE:
        return {"ok": False, "message": f"Quá nhiều URL (tối đa {MAX_BATCH_SIZE})."}

    results = []
    errors = []

    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            original_text = extract_text(url)
            if not original_text.strip():
                errors.append(f"{url}: không trích xuất được nội dung")
                continue

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
                    source_type="url",
                    title=title,
                    source_name=url[:255],
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
                    for tn in tag_names:
                        tag, _ = Tag.objects.get_or_create(name=tn)
                        all_tags.append(tag)
                    summary.tags.add(*all_tags)
                SummarySentence.objects.bulk_create(
                    [
                        SummarySentence(summary=summary, sentence_text=s, sentence_index=i)
                        for i, s in enumerate(result["sentences"], 1)
                    ]
                )

            results.append({
                "id": summary.id,
                "title": summary.title,
                "source_url": url,
                "method": method,
                "language": result["language"],
                "ratio": ratio,
                "summary": result["summary"],
                "keywords": result["keywords"],
            })

        except Exception as exc:  # noqa: BLE001
            logger.exception("Batch URL failed: %s", url)
            errors.append(f"{url}: {str(exc)}")

    return {
        "ok": True,
        "processed": len(results),
        "total": len([u for u in urls if u.strip()]),
        "results": results,
        "errors": errors,
    }