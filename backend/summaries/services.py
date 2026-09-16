"""Business logic services for summarization."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from celery.exceptions import CeleryError
from django.conf import settings
from django.core.cache import cache

from .models import _cleanup_uploaded_file
from .signing import decrypt_value
from .tasks import process_summary_task

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}
TASK_OWNER_TIMEOUT = 60 * 60


class SummaryService:
    """Handle summarization workflow."""

    def __init__(self, user):
        self.user = user

    def validate_and_prepare(
        self,
        source_type: str,
        method: str,
        ratio: float,
        text: str = "",
        source_url: str = "",
        uploaded_file=None,
    ) -> dict:
        """Validate input and prepare task arguments. Returns dict with task args or error."""
        errors = {}

        # Rate limit check
        cache_key = f"rate_limit:{self.user.id}"
        rate_limit_seconds = getattr(settings, "RATE_LIMIT_SECONDS", 5)
        if rate_limit_seconds > 0 and not cache.add(cache_key, True, rate_limit_seconds):
            msg = f"Vui lòng đợi {rate_limit_seconds} giây trước khi gửi yêu cầu tiếp theo."
            return {"ok": False, "message": msg, "status": 429}

        file_path = ""
        user_api_key = ""

        if source_type == "text":
            text = text.strip()
            if not text:
                errors["text"] = ["Nhập văn bản cần tóm tắt."]
        elif source_type == "url":
            if not source_url:
                errors["source_url"] = ["Nhập URL hợp lệ."]
        elif source_type == "file":
            if not uploaded_file:
                errors["upload"] = ["Chọn tệp để tóm tắt."]
            elif uploaded_file.size > MAX_FILE_SIZE:
                msg = "Dung lượng tệp vượt quá 10MB. Vui lòng chọn tệp nhỏ hơn."
                return {"ok": False, "message": msg, "status": 400}
            else:
                safe_name = Path(uploaded_file.name).name
                file_ext = Path(safe_name).suffix.lower()
                if file_ext not in ALLOWED_EXTS:
                    msg = f"Định dạng tệp không được hỗ trợ: {file_ext}"
                    return {"ok": False, "message": msg, "status": 400}
                # Check content
                first_chunk = b""
                for chunk in uploaded_file.chunks():
                    first_chunk = chunk
                    break
                if not first_chunk.strip():
                    msg = "Không thể trích xuất nội dung từ nguồn đã chọn."
                    return {"ok": False, "message": msg, "status": 400}
                uploaded_file.seek(0)
                temp_dir = Path(settings.MEDIA_ROOT) / "uploads"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / f"{uuid4().hex}_{safe_name}"
                with temp_path.open("wb+") as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                file_path = str(temp_path.relative_to(settings.MEDIA_ROOT))
        else:
            return {"ok": False, "message": "Không có nội dung để tóm tắt.", "status": 400}

        if errors:
            return {"ok": False, "errors": errors, "status": 400}

        # Validate Gemini API key
        if method == "gemini":
            system_key = getattr(settings, "GEMINI_API_KEY", "")
            user_key = ""
            if hasattr(self.user, "setting") and self.user.setting.gemini_api_key:
                user_key = decrypt_value(self.user.setting.gemini_api_key)
            if not system_key and not user_key:
                msg = (
                    "Thiếu GEMINI_API_KEY. Vui lòng cấu hình trong settings cá nhân hoặc file .env."
                )
                return {"ok": False, "message": msg, "status": 400}
            user_api_key = user_key

        return {
            "ok": True,
            "task_args": {
                "user_id": self.user.id,
                "source_type": source_type,
                "method": method,
                "ratio": ratio,
                "text": text,
                "source_url": source_url,
                "file_path": file_path,
                "user_api_key": user_api_key,
            },
        }

    def create_summary(self, source_type: str, method: str, ratio: float, **kwargs):
        """Create summary (async in production, sync in test/debug)."""
        validation = self.validate_and_prepare(source_type, method, ratio, **kwargs)
        if not validation["ok"]:
            return validation

        task_args = validation["task_args"]

        # Test/debug mode: run synchronously
        if os.getenv("DJANGO_TEST") == "1" or getattr(settings, "DEBUG", False):
            result = process_summary_task.apply(args=(), kwargs=task_args)
            task_result = result.result
            status = 200 if task_result.get("ok") else 400
            return {**task_result, "status": status}

        # Production: queue async task
        try:
            task = process_summary_task.delay(**task_args)
        except CeleryError:
            return {
                "ok": False,
                "message": "Dịch vụ xử lý nền hiện không khả dụng. Vui lòng thử lại sau.",
                "status": 503,
            }
        cache.set(f"task_owner:{task.id}", self.user.id, TASK_OWNER_TIMEOUT)
        return {"ok": True, "task_id": task.id}

    def cleanup_file(self, file_path: str) -> None:
        """Clean up uploaded file on error."""
        if file_path:
            _cleanup_uploaded_file(file_path)
