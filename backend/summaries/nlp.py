from __future__ import annotations

import html
import json
import re
import time as time_module
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    import requests

from django.conf import settings

try:
    import chardet
except ImportError:
    chardet = None

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

# Chữ hoa tiếng Việt (nằm ngoài khoảng A-Z của regex ASCII).
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

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}
STOP_WORDS_PATH = Path(__file__).resolve().parent / "stopwords.txt"

MAX_GEMINI_CHARS = 50000
GEMINI_RETRY_MAX = 3


class RegexTokenizer:
    def to_sentences(self, text: str) -> list[str]:
        return split_sentences(text)

    def to_words(self, sentence: str) -> list[str]:
        return split_words(sentence)


_TOKENIZER = RegexTokenizer()

_HTTP_SESSION: requests.Session | None = None


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        import requests

        _HTTP_SESSION = requests.Session()
        _HTTP_SESSION.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            }
        )
    return _HTTP_SESSION


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


def truncate_text(text: str, max_chars: int = MAX_GEMINI_CHARS) -> str:
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
    for keyword in sorted(keywords, key=len, reverse=True):
        pattern = re.compile(rf"\b({re.escape(keyword)})\b", re.IGNORECASE)
        text = pattern.sub(lambda m: f"\x00HL\x00{html.escape(m.group(1))}\x00/HL\x00", text)
    return html.escape(text).replace("\x00HL\x00", "<mark>").replace("\x00/HL\x00", "</mark>")


def generate_title(summary: str, source_name: str = "") -> str:
    if source_name:
        return f"Tóm tắt {source_name}"[:255]
    sentences = split_sentences(summary)
    return _title_from_sentences(sentences)


def _missing_dependency(package_name: str, feature: str) -> ValueError:
    return ValueError(
        f"Thiếu thư viện '{package_name}' để dùng {feature}. "
        "Hãy chạy 'pip install -r requirements.txt'."
    )


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


def _build_summary_result(summary: str, language: str, original_text: str) -> dict[str, Any]:
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


def _title_from_sentences(sentences: list[str]) -> str:
    if not sentences:
        return "Tóm tắt tài liệu"
    title = sentences[0][:120]
    if not title.endswith((".", "!", "?")):
        title += "."
    return title


def textrank_summarize(text: str, ratio: float = 0.2, language: str = "english") -> dict[str, Any]:
    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.summarizers.text_rank import TextRankSummarizer
    except ImportError as exc:
        raise _missing_dependency("sumy", "phương pháp tóm tắt TextRank") from exc

    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Nội dung văn bản đang rỗng.")

    parser = PlaintextParser.from_string(normalized, _TOKENIZER)
    summarizer = TextRankSummarizer()
    summarizer.stop_words = load_stop_words()

    total_sentences = max(1, len(parser.document.sentences))
    sentence_count = max(1, min(total_sentences, int(total_sentences * ratio) or 1))
    summary_sentences = summarizer(parser.document, sentence_count)
    summary = " ".join(str(sentence) for sentence in summary_sentences).strip()
    if not summary:
        all_sentences = split_sentences(normalized)
        summary = " ".join(all_sentences[:sentence_count])

    return _build_summary_result(summary, language, normalized)


def gemini_summarize(
    text: str, ratio: float = 0.2, language: str = "english", user_api_key: str = ""
) -> dict[str, Any]:
    try:
        import requests
    except ImportError as exc:
        raise _missing_dependency("requests", "chức năng tóm tắt Gemini") from exc

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

    session = _get_http_session()
    last_error: Exception | None = None
    for attempt in range(GEMINI_RETRY_MAX):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=60)
        except requests.exceptions.Timeout:
            raise ValueError(
                "Gemini API không phản hồi sau 60 giây. Vui lòng thử lại sau."
            ) from None
        except requests.exceptions.ConnectionError:
            raise ValueError("Không thể kết nối tới Gemini API. Kiểm tra kết nối mạng.") from None

        if response.status_code == 403:
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
            raise ValueError(f"Gemini API lỗi: {msg[:200]}")

        if response.status_code in (429, 502, 503):
            last_error = ValueError(f"Gemini API lỗi {response.status_code}: {response.text[:100]}")
            if attempt < GEMINI_RETRY_MAX - 1:
                wait = 2 ** (attempt + 1)
                time_module.sleep(wait)
                continue

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
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
        raise ValueError(
            "Gemini API trả về định dạng không mong đợi. "
            "Có thể nội dung đầu vào quá dài hoặc API đã thay đổi."
        ) from exc

    if not summary:
        raise ValueError("Gemini trả về nội dung tóm tắt rỗng.")

    return _build_summary_result(summary, language, text)


def _extract_text_from_txt(file_path: Path) -> str:
    if chardet is None:
        raise _missing_dependency("chardet", "đọc tệp văn bản")

    raw = file_path.read_bytes()
    encoding = chardet.detect(raw).get("encoding") or "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_text_from_docx(file_path: Path) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:
        raise _missing_dependency("python-docx", "đọc tệp .docx") from exc

    document = DocxDocument(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_text_from_pdf(file_path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise _missing_dependency("PyMuPDF", "đọc tệp .pdf") from exc

    text = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text.append(page.get_text())
    return "\n".join(text)


def _extract_text_from_epub(file_path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise _missing_dependency("beautifulsoup4", "đọc nội dung EPUB") from exc

    try:
        from ebooklib import epub
    except ImportError as exc:
        raise _missing_dependency("ebooklib", "đọc tệp .epub") from exc

    book = epub.read_epub(str(file_path))
    content = []
    for item in book.get_items():
        soup = BeautifulSoup(item.get_content(), "html.parser")
        content.append(soup.get_text(separator=" ", strip=True))
    return "\n".join(content)


def extract_text_from_url(url: str) -> str:
    try:
        import requests
    except ImportError as exc:
        raise _missing_dependency("requests", "đọc nội dung từ URL") from exc

    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise _missing_dependency("beautifulsoup4", "đọc nội dung từ URL") from exc

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL không hợp lệ.")

    session = _get_http_session()
    try:
        response = session.get(
            url,
            timeout=25,
            allow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi,en;q=0.9",
            },
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise ValueError("Không thể tải URL: yêu cầu đã hết thời gian chờ.") from None
    except requests.exceptions.ConnectionError:
        raise ValueError("Không thể kết nối tới URL. Kiểm tra địa chỉ hoặc kết nối mạng.") from None
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise ValueError(f"URL trả về lỗi HTTP {status}.") from None

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        if "text/plain" in content_type:
            return response.text
        raise ValueError(f"URL không phải trang HTML (Content-Type: {content_type}).")

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "meta", "link", "nav", "footer", "header", "aside"]
    ):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    if not text.strip():
        raise ValueError("Không trích xuất được nội dung từ URL.")
    return text


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
