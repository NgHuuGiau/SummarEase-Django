"""Tao chung chi self-signed cho dev HTTPS (SAN: localhost, 127.0.0.1)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

SSLDIR = Path(__file__).resolve().parents[1] / "backend" / "ssl"


def main() -> None:
    SSLDIR.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(_ip("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    (SSLDIR / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    (SSLDIR / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"OK: {SSLDIR / 'cert.pem'} (SAN: localhost, 127.0.0.1)")


def _ip(s: str):
    import ipaddress

    return ipaddress.ip_address(s)


if __name__ == "__main__":
    sys.exit(main())