from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import chardet
import fitz
import requests
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from ebooklib import epub
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.text_rank import TextRankSummarizer


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
}

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
}

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}
STOP_WORDS_PATH = Path(__file__).resolve().parent / "stopwords.txt"


class RegexTokenizer:
    def to_sentences(self, text: str) -> list[str]:
        return split_sentences(text)

    def to_words(self, sentence: str) -> list[str]:
        return split_words(sentence)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\r\n]+", " ", text)).strip()


def detect_language(text: str) -> str:
    lowered = text.lower()
    ascii_text = re.sub(r"[^a-zA-Z0-9\s]", " ", lowered)
    words = ascii_text.split()
    vi_score = sum(1 for word in words if word in VIETNAMESE_HINTS)
    en_score = sum(1 for word in words if word in ENGLISH_HINTS)
    return "vietnamese" if vi_score > en_score else "english"


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def split_words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text.lower(), flags=re.UNICODE)


def load_stop_words() -> set[str]:
    if not STOP_WORDS_PATH.exists():
        return set()
    return {
        line.strip().lower()
        for line in STOP_WORDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    stop_words = load_stop_words()
    words = [word for word in split_words(text) if len(word) > 2 and word not in stop_words]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]


def highlight_keywords(text: str, keywords: list[str]) -> str:
    highlighted = text
    for keyword in sorted(keywords, key=len, reverse=True):
        highlighted = re.sub(
            rf"\b({re.escape(keyword)})\b",
            r"<mark>\1</mark>",
            highlighted,
            flags=re.IGNORECASE,
        )
    return highlighted


def generate_title(summary: str, source_name: str = "") -> str:
    if source_name:
        return f"Tóm tắt {source_name}"[:255]
    first_sentence = split_sentences(summary)
    if first_sentence:
        return first_sentence[0][:120]
    return "Tóm tắt tài liệu"


def textrank_summarize(text: str, ratio: float = 0.2, language: str = "english") -> dict[str, Any]:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Nội dung văn bản đang rỗng.")

    parser = PlaintextParser.from_string(normalized, RegexTokenizer())
    summarizer = TextRankSummarizer()
    summarizer.stop_words = load_stop_words()

    total_sentences = max(1, len(parser.document.sentences))
    sentence_count = max(1, min(total_sentences, int(total_sentences * ratio) or 1))
    summary_sentences = summarizer(parser.document, sentence_count)
    summary = " ".join(str(sentence) for sentence in summary_sentences).strip()
    if not summary:
        summary = " ".join(split_sentences(normalized)[:sentence_count])

    keywords = extract_keywords(normalized)
    return {
        "language": language,
        "summary": summary,
        "highlighted_summary": highlight_keywords(summary, keywords),
        "keywords": keywords,
        "sentences": split_sentences(summary),
        "title": generate_title(summary),
    }


def gemini_summarize(text: str, ratio: float = 0.2, language: str = "english") -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Thiếu GEMINI_API_KEY.")

    prompt = (
        f"Tóm tắt văn bản sau bằng {language} với độ dài khoảng {ratio:.0%}. "
        "Trả về một bản tóm tắt rõ ý, ngắn gọn, dễ đọc."
        f"\n\nVăn bản:\n{text}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={api_key}"
    )
    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    summary = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    keywords = extract_keywords(text)
    return {
        "language": language,
        "summary": summary,
        "highlighted_summary": highlight_keywords(summary, keywords),
        "keywords": keywords,
        "sentences": split_sentences(summary),
        "title": generate_title(summary),
    }


def _extract_text_from_txt(file_path: Path) -> str:
    raw = file_path.read_bytes()
    encoding = chardet.detect(raw).get("encoding") or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_text_from_docx(file_path: Path) -> str:
    document = DocxDocument(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_text_from_pdf(file_path: Path) -> str:
    text = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text.append(page.get_text())
    return "\n".join(text)


def _extract_text_from_epub(file_path: Path) -> str:
    book = epub.read_epub(str(file_path))
    content = []
    for item in book.get_items():
        soup = BeautifulSoup(item.get_content(), "html.parser")
        content.append(soup.get_text(separator=" ", strip=True))
    return "\n".join(content)


def extract_text_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL khong hop le.")
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def extract_text(source: str | Path) -> str:
    if isinstance(source, str) and urlparse(source).scheme in {"http", "https"}:
        return extract_text_from_url(source)

    file_path = Path(source)
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Định dạng tệp không được hỗ trợ: {suffix}")
    if suffix in {".txt", ".md", ".markdown"}:
        return _extract_text_from_txt(file_path)
    if suffix == ".docx":
        return _extract_text_from_docx(file_path)
    if suffix == ".pdf":
        return _extract_text_from_pdf(file_path)
    return _extract_text_from_epub(file_path)
