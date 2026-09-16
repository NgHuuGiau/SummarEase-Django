import hashlib
import hmac
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify a backup manifest, SHA-256 checksum, and JSON dump"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to a timestamped backup directory")

    def handle(self, *args, **options):
        folder = Path(options["path"])
        try:
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            filename = manifest["database_dump"]
            expected_digest = manifest["sha256"]
            if (
                not isinstance(filename, str)
                or Path(filename).name != filename
                or "/" in filename
                or "\\" in filename
            ):
                raise ValueError("Invalid database dump filename")
            if not isinstance(expected_digest, str):
                raise ValueError("Invalid checksum")

            db_path = folder / filename
            contents = db_path.read_bytes()
            actual_digest = hashlib.sha256(contents).hexdigest()
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError("SHA-256 checksum does not match")
            if not isinstance(json.loads(contents), list):
                raise ValueError("Database dump must be a JSON list")
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise CommandError(f"Backup verification failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Backup verified: {db_path}"))
