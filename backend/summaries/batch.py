"""Batch summarization for multiple files/URLs."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model

from .persistence import summarize_and_persist
from .readers import extract_text

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_BATCH_SIZE = 20
MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50MB
MAX_EXTRACTED_SIZE = 200 * 1024 * 1024
ALLOWED_EXTS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}


def create_batch_from_zip(
    user, zip_file, method: str, ratio: float, user_api_key: str = ""
) -> dict:
    """Process a ZIP file containing multiple documents."""
    if zip_file.size > MAX_ZIP_SIZE:
        return {"ok": False, "message": "File ZIP vượt quá 50MB."}

    results = []
    errors = []
    processed = 0

    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            # Validate all files first
            file_list = []
            for name in zip_ref.namelist():
                if name.endswith("/") or name.startswith("__MACOSX"):
                    continue
                archive_path = PurePosixPath(name.replace("\\", "/"))
                if (
                    archive_path.is_absolute()
                    or ".." in archive_path.parts
                    or any(":" in part for part in archive_path.parts)
                ):
                    errors.append(f"{name}: đường dẫn không hợp lệ")
                    continue
                ext = Path(archive_path.name).suffix.lower()
                if ext not in ALLOWED_EXTS:
                    errors.append(f"{name}: định dạng không hỗ trợ ({ext})")
                    continue
                file_list.append(name)

            if not file_list:
                return {"ok": False, "message": "Không có tệp hợp lệ trong ZIP.", "errors": errors}

            if len(file_list) > MAX_BATCH_SIZE:
                msg = f"ZIP chứa quá nhiều tệp (tối đa {MAX_BATCH_SIZE})."
                return {"ok": False, "message": msg, "errors": errors}
            if sum(info.file_size for info in zip_ref.infolist()) > MAX_EXTRACTED_SIZE:
                return {"ok": False, "message": "Tổng dung lượng giải nén vượt quá 200MB."}
            for info in zip_ref.infolist():
                if info.file_size > 1_048_576 and info.compress_size * 100 < info.file_size:
                    return {
                        "ok": False,
                        "message": "ZIP có tỷ lệ nén bất thường, không được chấp nhận.",
                    }

            # Extract and process each file
            temp_dir = Path(settings.MEDIA_ROOT) / "batch_uploads" / uuid4().hex
            temp_dir.mkdir(parents=True, exist_ok=True)

            for name in file_list:
                try:
                    file_path = Path(zip_ref.extract(name, temp_dir)).resolve()
                    if not file_path.is_relative_to(temp_dir.resolve()):
                        errors.append(f"{name}: đường dẫn không hợp lệ")
                        continue

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
                    summary, result = summarize_and_persist(
                        user,
                        "file",
                        name,
                        original_text,
                        method,
                        ratio,
                        user_api_key=user_api_key,
                    )

                    results.append(
                        {
                            "id": summary.id,
                            "title": summary.title,
                            "file_name": name,
                            "method": method,
                            "language": result["language"],
                            "ratio": ratio,
                            "summary": result["summary"],
                            "keywords": result["keywords"],
                        }
                    )
                    processed += 1

                except Exception:  # noqa: BLE001
                    logger.exception("Batch item failed: %s", name)
                    errors.append(f"{name}: Không thể xử lý tệp này.")

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
    except Exception:  # noqa: BLE001
        logger.exception("Batch processing failed")
        return {
            "ok": False,
            "message": "Không thể xử lý lô tệp. Vui lòng thử lại sau.",
            "errors": errors,
        }


def create_batch_from_urls(
    user, urls: list, method: str, ratio: float, user_api_key: str = ""
) -> dict:
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
                errors.append("Không trích xuất được nội dung từ URL đã cung cấp.")
                continue

            summary, result = summarize_and_persist(
                user, "url", url, original_text, method, ratio, user_api_key=user_api_key
            )

            results.append(
                {
                    "id": summary.id,
                    "title": summary.title,
                    "source_url": url,
                    "method": method,
                    "language": result["language"],
                    "ratio": ratio,
                    "summary": result["summary"],
                    "keywords": result["keywords"],
                }
            )

        except Exception:  # noqa: BLE001
            logger.exception("Batch URL failed: %s", url)
            errors.append("Không thể xử lý URL đã cung cấp.")

    return {
        "ok": True,
        "processed": len(results),
        "total": len([u for u in urls if u.strip()]),
        "results": results,
        "errors": errors,
    }
