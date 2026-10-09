"""File and URL text extraction with SSRF protection."""

from __future__ import annotations

import atexit
import ipaddress
import logging
import socket
import threading
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

if TYPE_CHECKING:
    import requests


logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf", ".epub"}
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = 25
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_URL_LENGTH = 2048
MAX_ARCHIVE_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_DOCUMENT_PAGES = 500
MAX_EXTRACTED_CHARACTERS = 50_000


class TransientNetworkError(ValueError):
    """Sanitized network failure that can be retried by background tasks."""


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
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or any(ip in net for net in _BLOCKED_NETWORKS)
    )


def _resolve_and_validate(host: str) -> None:
    if not host:
        raise ValueError("URL redirect không hợp lệ.")
    # ponytail: chống DNS-rebinding đầy đủ (nối tới IP đã xác thực) gặp khó vì
    # urllib3 gắn chặt connect-host với SNI; thêm khi mục tiêu trở thành SSRF
    # nội bộ đáng giá. Hiện tại mọi hop đều re-resolve + chặn private IP.
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Không thể phân giải hostname: {host}") from exc
    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr = str(sockaddr[0])
        if _is_private_ip(addr):
            raise ValueError(
                f"URL trỏ tới địa chỉ nội bộ ({sockaddr[0]}). Không cho phép truy cập mạng nội bộ."
            )


# ── Thread-safe HTTP session ────────────────────────

_local = threading.local()


def _get_http_session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        import requests

        session = requests.Session()
        session.trust_env = False
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


def _close_http_session() -> None:
    """Close thread-local HTTP session on exit."""
    session = getattr(_local, "session", None)
    if session:
        session.close()
        _local.session = None


atexit.register(_close_http_session)


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

    _validate_archive_size(file_path)
    document = DocxDocument(file_path)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError("Tài liệu vượt quá giới hạn 50.000 ký tự.")
    return text


def _extract_text_from_pdf(file_path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError(
            "Thiếu thư viện 'PyMuPDF' để dùng đọc tệp .pdf. "
            "Hãy chạy 'pip install -r requirements.txt'."
        ) from exc

    text = []
    chars = 0
    with fitz.open(file_path) as pdf:
        if len(pdf) > MAX_DOCUMENT_PAGES:
            raise ValueError(f"PDF vượt quá giới hạn {MAX_DOCUMENT_PAGES} trang.")
        for page in pdf:
            page_text = page.get_text()
            text.append(page_text)
            chars += len(page_text)
            if chars > MAX_EXTRACTED_CHARACTERS:
                raise ValueError("Tài liệu vượt quá giới hạn 50.000 ký tự.")
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

    _validate_archive_size(file_path)
    book = epub.read_epub(str(file_path))
    content = []
    for item in book.get_items():
        soup = BeautifulSoup(item.get_content(), "html.parser")
        content.append(soup.get_text(separator=" ", strip=True))
    text = "\n".join(content)
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError("Tài liệu vượt quá giới hạn 50.000 ký tự.")
    return text


def _validate_archive_size(file_path: Path) -> None:
    try:
        with zipfile.ZipFile(file_path) as archive:
            infos = archive.infolist()
            if sum(info.file_size for info in infos) > MAX_ARCHIVE_EXPANDED_BYTES:
                raise ValueError("Tài liệu nén vượt quá giới hạn 50MB sau giải nén.")
            if any(
                info.file_size > 1_048_576 and info.file_size > info.compress_size * 100
                for info in infos
            ):
                raise ValueError("Tài liệu có tỷ lệ nén bất thường, không được chấp nhận.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Tệp tài liệu không hợp lệ hoặc bị hỏng.") from exc


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
    if len(url) > MAX_URL_LENGTH:
        raise ValueError("URL vượt quá giới hạn 2048 ký tự.")
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
                stream=True,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "vi,en;q=0.9",
                },
            )
        except requests.exceptions.Timeout:
            raise TransientNetworkError(
                "Không thể tải URL: yêu cầu đã hết thời gian chờ."
            ) from None
        except requests.exceptions.ConnectionError:
            raise TransientNetworkError(
                "Không thể kết nối tới URL. Kiểm tra địa chỉ hoặc kết nối mạng."
            ) from None

        if response is not None and response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location", "")
            if redirect_url:
                response.close()
                last_url = urljoin(last_url, redirect_url)
                parsed_redirect = urlparse(last_url)
                if parsed_redirect.scheme not in {"http", "https"}:
                    raise ValueError("URL redirect không hợp lệ.")
                _resolve_and_validate(parsed_redirect.hostname or "")
                continue

        break
    else:
        raise ValueError("URL có quá nhiều lần chuyển hướng.")

    if response is None:
        raise ValueError("Không thể tải URL.")

    try:
        if response.status_code >= 400:
            raise ValueError(f"URL trả về lỗi HTTP {response.status_code}.")
        if int(response.headers.get("Content-Length", 0) or 0) > MAX_RESPONSE_BYTES:
            raise ValueError("Nội dung URL vượt quá giới hạn 20MB.")
        content_type = response.headers.get("Content-Type", "")
        is_plain_text = "text/plain" in content_type
        if (
            not is_plain_text
            and "text/html" not in content_type
            and "application/xhtml" not in content_type
        ):
            raise ValueError(f"URL không phải trang HTML (Content-Type: {content_type}).")

        body = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ValueError("Nội dung URL vượt quá giới hạn 20MB.")
        except requests.exceptions.Timeout:
            raise TransientNetworkError(
                "Không thể tải URL: yêu cầu đã hết thời gian chờ."
            ) from None
        except requests.exceptions.RequestException:
            raise TransientNetworkError(
                "Không thể kết nối tới URL. Kiểm tra địa chỉ hoặc kết nối mạng."
            ) from None
    finally:
        response.close()

    encoding = requests.utils.get_encoding_from_headers(response.headers) or "utf-8"
    try:
        text = body.decode(encoding, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    if is_plain_text:
        return text

    soup = BeautifulSoup(text, "html.parser")
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
