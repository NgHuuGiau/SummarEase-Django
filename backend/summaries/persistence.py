"""Database persistence for generated summaries."""

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from .models import Document, Summary, SummarySentence, Tag


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
            tags = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
            summary.tags.add(*tags)
        SummarySentence.objects.bulk_create(
            [
                SummarySentence(summary=summary, sentence_text=sentence, sentence_index=index)
                for index, sentence in enumerate(result["sentences"], start=1)
            ]
        )
    return summary
