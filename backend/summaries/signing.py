import base64
import hashlib
import logging

from django.conf import settings

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None  # type: ignore
    logging.warning("cryptography not installed — API keys stored in plaintext")


logger = logging.getLogger(__name__)


def _get_fernet() -> "Fernet":
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    if not value or Fernet is None:
        if Fernet is None and value:
            logger.warning("encrypt_value called without cryptography — returning plaintext")
        return value if Fernet is None else ""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    if not encrypted or Fernet is None:
        if Fernet is None and encrypted:
            logger.warning("decrypt_value called without cryptography — returning raw value")
        return encrypted if Fernet is None else ""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return encrypted
