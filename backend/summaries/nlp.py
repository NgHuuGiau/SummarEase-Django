"""Text summarization using TextRank and Gemini AI."""

from __future__ import annotations

import json
import logging
import time as time_module
from functools import lru_cache
from typing import Any

from django.conf import settings

from .nlp_utils import (
    build_summary_result,
    load_stop_words,
    split_sentences,
    truncate_text,
)

logger = logging.getLogger(__name__)

GEMINI_RETRY_MAX = 3


def _build_prompt(text: str, ratio: float, language: str) -> str:
    if language == "vietnamese":
        length_guide = _ratio_to_vietnamese(ratio)
        return (
            f"Hãy tóm tắt văn bản sau bằng tiếng Việt, "
            f"{length_guide}. "
            "Chỉ giữ lại các ý chính, thông tin quan trọng, số liệu nổi bật. "
            "Viết thành một đoạn văn mạch lạc, dễ đọc. "
            "KHÔNG thêm bình luận, KHÔNG thêm lời dẫn, KHÔNG thêm câu hỏi. "
            "CHỈ trả về nội dung tóm tắt."
            f"\n\nVăn bản:\n{text}"
        )

    length_pct = f"{ratio:.0%}"
    return (
        f"Summarize the following text in English, "
        f"keeping approximately {length_pct} of the original content. "
        "Preserve the main ideas, key arguments, important data, and conclusions. "
        "Write a coherent, readable paragraph. "
        "Do NOT add commentary, Do NOT add meta-references, Do NOT ask questions. "
        "Return ONLY the summary content."
        f"\n\nText:\n{text}"
    )


def _ratio_to_vietnamese(ratio: float) -> str:
    if ratio <= 0.15:
        return "tóm tắt thật ngắn gọn, chỉ giữ lại luận điểm chính nhất"
    if ratio <= 0.3:
        return f"tóm tắt khoảng {ratio:.0%} độ dài gốc, giữ các ý chính"
    if ratio <= 0.5:
        return f"tóm tắt khoảng {ratio:.0%} độ dài gốc, giữ nội dung quan trọng"
    return f"rút gọn còn khoảng {ratio:.0%}, giữ hầu hết thông tin"


def textrank_summarize(text: str, ratio: float = 0.2, language: str = "english") -> dict[str, Any]:
    try:
        from sumy.parsers.plaintext import PlaintextParser  # noqa: F401
        from sumy.summarizers.text_rank import TextRankSummarizer  # noqa: F401
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'sumy' để dùng phương pháp tóm tắt TextRank. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    from .nlp_utils import normalize_text

    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Nội dung văn bản đang rỗng.")

    # ponytail: cache theo (chuẩn hoá, tỉ lệ, ngôn ngữ); maxsize giới hạn bộ nhớ,
    # đổi sang Redis cache nếu tải trọng tăng.
    return _textrank_cached(normalized, ratio, language)


@lru_cache(maxsize=64)
def _textrank_cached(normalized: str, ratio: float, language: str) -> dict[str, Any]:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.text_rank import TextRankSummarizer

    from .nlp_utils import RegexTokenizer

    tokenizer = RegexTokenizer()
    parser = PlaintextParser.from_string(normalized, tokenizer)
    summarizer = TextRankSummarizer()
    summarizer.stop_words = load_stop_words()

    total_sentences = max(1, len(parser.document.sentences))
    sentence_count = max(1, min(total_sentences, int(total_sentences * ratio) or 1))
    summary_sentences = summarizer(parser.document, sentence_count)
    summary = " ".join(str(sentence) for sentence in summary_sentences).strip()
    if not summary:
        all_sentences = split_sentences(normalized)
        summary = " ".join(all_sentences[:sentence_count])

    return build_summary_result(summary, language, normalized)


def gemini_summarize(
    text: str, ratio: float = 0.2, language: str = "english", user_api_key: str = ""
) -> dict[str, Any]:
    try:
        import requests
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'requests' để dùng chức năng tóm tắt Gemini. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    api_key = user_api_key or settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError(
            "Thiếu GEMINI_API_KEY. Vui lòng cấu hình trong settings cá nhân hoặc file .env."
        )

    model = settings.GEMINI_MODEL
    truncated = truncate_text(text)
    prompt = _build_prompt(truncated, ratio, language)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    from .readers import _get_http_session

    session = _get_http_session()
    last_error: Exception | None = None

    logger.info(
        "gemini_summarize called: model=%s, text_len=%d, ratio=%.2f, language=%s",
        model,
        len(text),
        ratio,
        language,
    )

    for attempt in range(GEMINI_RETRY_MAX):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=60)
        except requests.exceptions.Timeout:
            logger.error(
                "Gemini API timeout after 60s (attempt %d/%d)",
                attempt + 1, GEMINI_RETRY_MAX,
            )
            raise ValueError(
                "Gemini API không phản hồi sau 60 giây. Vui lòng thử lại sau."
            ) from None
        except requests.exceptions.ConnectionError:
            logger.error(
                "Gemini API connection error (attempt %d/%d)",
                attempt + 1, GEMINI_RETRY_MAX,
            )
            raise ValueError("Không thể kết nối tới Gemini API. Kiểm tra kết nối mạng.") from None

        if response.status_code == 403:
            logger.error("Gemini API 403: invalid or inactive API key")
            raise ValueError(
                "Gemini API trả về lỗi 403: API key không hợp lệ hoặc chưa được kích hoạt. "
                "Kiểm tra GEMINI_API_KEY tại https://aistudio.google.com/apikey"
            )
        if response.status_code == 400:
            try:
                err_detail = response.json()
                msg = err_detail.get("error", {}).get("message", str(response.text))
            except (json.JSONDecodeError, KeyError, TypeError):
                msg = str(response.text)
            logger.error("Gemini API 400: %s", msg[:200])
            raise ValueError(f"Gemini API lỗi: {msg[:200]}")

        if response.status_code in (429, 502, 503):
            last_error = ValueError(f"Gemini API lỗi {response.status_code}: {response.text[:100]}")
            logger.warning(
                "Gemini API %d (attempt %d/%d), retrying in %ds",
                response.status_code,
                attempt + 1,
                GEMINI_RETRY_MAX,
                2 ** (attempt + 1),
            )
            if attempt < GEMINI_RETRY_MAX - 1:
                wait = 2 ** (attempt + 1)
                time_module.sleep(wait)
                continue

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.error("Gemini API HTTP %d", response.status_code)
            raise ValueError(
                f"Gemini API lỗi HTTP {response.status_code}: {response.text[:200]}"
            ) from None
        break
    else:
        raise last_error or ValueError("Gemini API không phản hồi sau nhiều lần thử.")

    try:
        payload = response.json()
        summary = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.error("Gemini API unexpected response format: %s", str(exc))
        raise ValueError(
            "Gemini API trả về định dạng không mong đợi. "
            "Có thể nội dung đầu vào quá dài hoặc API đã thay đổi."
        ) from exc

    if not summary:
        raise ValueError("Gemini trả về nội dung tóm tắt rỗng.")

    logger.info("gemini_summarize done: summary_len=%d", len(summary))
    return build_summary_result(summary, language, text)
