import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backup DB (dumpdata JSON) + optional media to a timestamped folder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dest",
            default=str(Path(settings.BACKEND_DIR) / "backups"),
            help="Destination folder (default: backend/backups)",
        )
        parser.add_argument(
            "--include-media",
            action="store_true",
            help="Also copy the entire MEDIA_ROOT",
        )

    def handle(self, *args, **options):
        dest = Path(options["dest"])
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = dest / stamp
        folder.mkdir(parents=True, exist_ok=True)

        db_path = folder / "db.json"
        with open(db_path, "w", encoding="utf-8") as fh:
            call_command("dumpdata", stdout=fh)
        self.stdout.write(self.style.SUCCESS(f"==> DB backup: {db_path}"))

        if options["include_media"]:
            media = Path(settings.MEDIA_ROOT)
            if media.exists():
                shutil.copytree(media, folder / "media", dirs_exist_ok=True)
                self.stdout.write(self.style.SUCCESS(f"==> Media backup: {folder / 'media'}"))

        self.stdout.write(self.style.SUCCESS(f"==> Backup complete: {folder}"))
