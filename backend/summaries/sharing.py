"""Shareable public links for summaries."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .models import Summary

# Default expiry: 7 days
DEFAULT_EXPIRY_DAYS = 7

# Separate signing key for share links (can be same as API_ENCRYPTION_KEY or different)
SHARE_SECRET_KEY = cast(
    str,
    getattr(settings, "SHARE_SECRET_KEY", None)
    or getattr(settings, "API_ENCRYPTION_KEY", "")
    or __import__("secrets").token_urlsafe(32),
)


def generate_share_token(summary: Summary, expiry_days: int = DEFAULT_EXPIRY_DAYS) -> str:
    """Generate a signed token for sharing a summary."""
    payload = {
        "summary_id": summary.id,
        "exp": int((timezone.now() + timedelta(days=expiry_days)).timestamp()),
        "iat": int(timezone.now().timestamp()),
    }

    # Create token: base64(payload) + "." + base64(signature)
    payload_bytes = base64.urlsafe_b64encode(str(payload).encode()).rstrip(b"=")

    signature = hmac.new(SHARE_SECRET_KEY.encode(), payload_bytes, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")

    return f"{payload_bytes.decode()}.{signature_b64.decode()}"


def verify_share_token(token: str) -> dict | None:
    """Verify and decode a share token. Returns payload dict or None if invalid."""
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    # Verify signature
    expected_sig = hmac.new(
        SHARE_SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
    ).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

    if not hmac.compare_digest(signature_b64, expected_sig_b64):
        return None

    # Decode payload
    try:
        # Add padding if needed
        padding = 4 - (len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * padding)
        import json

        payload = json.loads(payload_bytes.decode())
    except Exception:
        return None

    # Check expiry
    if payload.get("exp", 0) < time.time():
        return None

    return payload


def get_share_url(summary: Summary, request=None, expiry_days: int = DEFAULT_EXPIRY_DAYS) -> str:
    """Generate full shareable URL for a summary."""
    token = generate_share_token(summary, expiry_days)
    path = reverse("shared_summary", kwargs={"token": token})
    if request:
        return request.build_absolute_uri(path)
    return path


def get_shared_summary(request, token: str) -> Summary:
    """Retrieve summary from share token (raises 404 if invalid)."""
    payload = verify_share_token(token)
    if not payload:
        raise Http404("Liên kết chia sẻ không hợp lệ hoặc đã hết hạn.")

    summary_id = payload.get("summary_id")
    if not summary_id:
        raise Http404("Liên kết chia sẻ không hợp lệ.")

    # Allow access to any summary via share link (no user filter)
    summary = get_object_or_404(
        Summary.objects.select_related("document", "user").prefetch_related("tags", "sentences"),
        pk=summary_id,
    )
    return summary
