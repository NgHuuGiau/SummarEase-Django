"""NLP utilities: tokenization, language detection, keyword extraction."""

from __future__ import annotations

import html
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

VIETNAMESE_HINTS = {
    "va",
    "cua",
    "trong",
    "voi",
    "cho",
    "duoc",
    "nhung",
    "cac",
    "la",
    "nay",
    "mot",
    "nguoi",
    "khong",
    "co",
    "them",
    "ve",
    "hoac",
    "neu",
    "rat",
    "sau",
    "khi",
    "tai",
    "tu",
}

VIETNAMESE_CHARS = re.compile(
    "[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)

VIETNAMESE_UPPERCASE = "ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"

_SENTENCE_START_CHARS = VIETNAMESE_UPPERCASE + r"A-Z0-9\"'([{"

ENGLISH_HINTS = {
    "the",
    "be",
    "to",
    "of",
    "and",
    "that",
    "have",
    "for",
    "not",
    "with",
    "this",
    "from",
    "but",
    "they",
    "which",
    "would",
    "there",
    "their",
    "what",
    "about",
    "been",
}

STOP_WORDS_PATH = Path(__file__).resolve().parent / "stopwords.txt"


class RegexTokenizer:
    def to_sentences(self, text: str) -> list[str]:
        return split_sentences(text)

    def to_words(self, sentence: str) -> list[str]:
        return split_words(sentence)


_TOKENIZER = RegexTokenizer()


def normalize_text(text: str) -> str:
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def detect_language(text: str) -> str:
    if VIETNAMESE_CHARS.search(text):
        return "vietnamese"

    lowered = text.lower()
    ascii_text = re.sub(r"[^a-z0-9\s]", " ", lowered)
    words = [w for w in ascii_text.split() if len(w) > 1]
    if not words:
        return "english"
    vi_score = sum(1 for word in words if word in VIETNAMESE_HINTS)
    en_score = sum(1 for word in words if word in ENGLISH_HINTS)
    return "vietnamese" if vi_score > en_score else "english"


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"(?<!\w)(Mr|Mrs|Ms|Dr|Prof|St|vs|etc)\.(?=\s|$)", r"\1<DOT>", text, flags=re.IGNORECASE
    )
    text = re.sub(r"\b([Tt]p|[Tt]r|[Tt]h|[Nn]xb|[Tt]g)\.(?=\s|$)", r"\1<DOT>", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[" + _SENTENCE_START_CHARS + r"])", text)
    sentences = [s.strip() for s in parts if s.strip()]
    return [s.replace("<DOT>", ".") for s in sentences]


def split_words(text: str) -> list[str]:
    return re.findall(r"\b[\w'–-]+\b", text.lower(), flags=re.UNICODE)


def truncate_text(text: str, max_chars: int = 50000) -> str:
    if len(text) <= max_chars:
        return text
    sentences = split_sentences(text)
    truncated = []
    chars = 0
    for sentence in sentences:
        if chars + len(sentence) > max_chars and truncated:
            break
        truncated.append(sentence)
        chars += len(sentence) + 1
    result = " ".join(truncated)
    return result[:max_chars] if len(result) > max_chars else result


@lru_cache(maxsize=1)
def load_stop_words() -> frozenset[str]:
    if not STOP_WORDS_PATH.exists():
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in STOP_WORDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    stop_words = load_stop_words()
    words = [word for word in split_words(text) if len(word) > 2 and word not in stop_words]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]


def highlight_keywords(text: str, keywords: list[str]) -> str:
    kw_start = "\x00KWSTART\x00"
    kw_end = "\x00KWEND\x00"
    for keyword in sorted(keywords, key=len, reverse=True):
        pattern = re.compile(rf"\b({re.escape(keyword)})\b", re.IGNORECASE)
        text = pattern.sub(
            lambda m: f"{kw_start}{html.escape(m.group(1))}{kw_end}", text
        )
    text = html.escape(text)
    text = text.replace(kw_start, "<mark>").replace(kw_end, "</mark>")
    return text


def generate_title(summary: str, source_name: str = "") -> str:
    if source_name:
        return f"Tóm tắt {source_name}"[:255]
    sentences = split_sentences(summary)
    return _title_from_sentences(sentences)


def _title_from_sentences(sentences: list[str]) -> str:
    if not sentences:
        return "Tóm tắt tài liệu"
    title = sentences[0][:120]
    if not title.endswith((".", "!", "?")):
        title += "."
    return title


def build_summary_result(summary: str, language: str, original_text: str) -> dict[str, Any]:
    keywords = extract_keywords(original_text)
    sentences = split_sentences(summary)
    return {
        "language": language,
        "summary": summary,
        "highlighted_summary": highlight_keywords(summary, keywords),
        "keywords": keywords,
        "sentences": sentences,
        "title": generate_title(summary) if not sentences else _title_from_sentences(sentences),
    }
