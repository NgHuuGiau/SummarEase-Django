"""Database persistence for generated summaries."""

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils.text import slugify

from .models import Document, Summary, SummarySentence, Tag
from .nlp import gemini_summarize, textrank_summarize
from .nlp_utils import detect_language


def summarize_and_persist(
    user: AbstractBaseUser,
    source_type: str,
    source_name: str,
    original_text: str,
    method: str,
    ratio: float,
    user_api_key: str = "",
    uploaded_file: str = "",
) -> tuple[Summary, dict[str, Any]]:
    """Run the chosen summarizer and persist the result. Returns (summary, result)."""
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
        uploaded_file=uploaded_file,
    )
    return summary, result


def persist_summary(
    user: AbstractBaseUser,
    source_type: str,
    source_name: str,
    original_text: str,
    method: str,
    ratio: float,
    result: dict[str, Any],
    uploaded_file: str = "",
) -> Summary:
    """Persist a document and its generated summary atomically."""
    title = result["title"][:255]
    with transaction.atomic():
        document = Document.objects.create(
            user=user,
            source_type=source_type,
            title=title,
            source_name=source_name[:255],
            uploaded_file=uploaded_file,
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
        tag_names = list(dict.fromkeys(keyword[:100] for keyword in result["keywords"]))
        if tag_names:
            # Bulk upsert: 2 queries total instead of N get_or_create round-trips.
            # ignore_conflicts covers concurrent inserts; re-fetch picks up race winners.
            existing = {tag.name: tag for tag in Tag.objects.filter(name__in=tag_names)}
            missing = [name for name in tag_names if name not in existing]
            if missing:
                Tag.objects.bulk_create(
                    [Tag(name=name, slug=slugify(name, allow_unicode=True)) for name in missing],
                    ignore_conflicts=True,
                )
                existing = {tag.name: tag for tag in Tag.objects.filter(name__in=tag_names)}
            summary.tags.add(*[existing[name] for name in tag_names if name in existing])
        SummarySentence.objects.bulk_create(
            [
                SummarySentence(summary=summary, sentence_text=sentence, sentence_index=index)
                for index, sentence in enumerate(result["sentences"], start=1)
            ]
        )
    return summary
