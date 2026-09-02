"""File and URL text extraction with SSRF protection."""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    import requests


logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}
MAX_GEMINI_CHARS = 50000
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = 25

# ── SSRF protection ─────────────────────────────────
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in _BLOCKED_NETWORKS)


def _resolve_and_validate(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Không thể phân giải hostname: {host}") from exc
    for _family, _, _, _, sockaddr in infos:
        if _is_private_ip(sockaddr[0]):
            raise ValueError(
                f"URL trỏ tới địa chỉ nội bộ ({sockaddr[0]}). "
                "Không cho phép truy cập mạng nội bộ."
            )


# ── Thread-safe HTTP session ────────────────────────
_local = threading.local()


def _get_http_session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        import requests

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            }
        )
        _local.session = session
    return session


# ── File readers ────────────────────────────────────


def _extract_text_from_txt(file_path: Path) -> str:
    try:
        import chardet
    except ImportError:
        chardet = None  # type: ignore

    raw = file_path.read_bytes()
    if chardet is not None:
        encoding = chardet.detect(raw).get("encoding") or "utf-8"
    else:
        encoding = "utf-8"
    return raw.decode(encoding, errors="ignore")


def _extract_text_from_docx(file_path: Path) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'python-docx' để dùng đọc tệp .docx. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    document = DocxDocument(file_path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_text_from_pdf(file_path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'PyMuPDF' để dùng đọc tệp .pdf. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    text = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text.append(page.get_text())
    return "\n".join(text)


def _extract_text_from_epub(file_path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'beautifulsoup4' để dùng đọc nội dung EPUB. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    try:
        from ebooklib import epub
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'ebooklib' để dùng đọc tệp .epub. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

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
        raise ValueError(
            "Thiếu thư viện 'requests' để dùng đọc nội dung từ URL. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'beautifulsoup4' để dùng đọc nội dung từ URL. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL không hợp lệ.")

    _resolve_and_validate(parsed.hostname or parsed.netloc)

    session = _get_http_session()
    response = None
    last_url = url

    for _ in range(MAX_REDIRECTS):
        try:
            response = session.get(
                last_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "vi,en;q=0.9",
                },
            )
        except requests.exceptions.Timeout:
            raise ValueError("Không thể tải URL: yêu cầu đã hết thời gian chờ.") from None
        except requests.exceptions.ConnectionError as exc:
            raise ValueError(
                "Không thể kết nối tới URL. Kiểm tra địa chỉ hoặc kết nối mạng."
            ) from exc

        if response is not None and response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            if redirect_url:
                _resolve_and_validate(urlparse(redirect_url).hostname or "")
                last_url = redirect_url
                continue

        break

    if response is None:
        raise ValueError("Không thể tải URL.")

    if response.status_code >= 400:
        raise ValueError(f"URL trả về lỗi HTTP {response.status_code}.")

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
