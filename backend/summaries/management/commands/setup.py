import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Setup project: migrate (does NOT auto-create any accounts)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-superuser",
            action="store_true",
            help="Create a default superuser if none exists",
        )
        parser.add_argument(
            "--username",
            default=os.getenv("DJANGO_SUPERUSER_USERNAME", "admin"),
        )
        parser.add_argument(
            "--password",
            default=os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin123"),
        )
        parser.add_argument(
            "--email",
            default=os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com"),
        )

    def handle(self, *args, **options):
        self.stdout.write("==> Running migrate...")
        call_command("migrate", "--noinput")

        if options["create_superuser"]:
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            if user_model.objects.filter(is_superuser=True).exists():
                self.stdout.write(self.style.WARNING("==> Superuser already exists, skipping."))
            else:
                user_model.objects.create_superuser(
                    username=options["username"],
                    password=options["password"],
                    email=options["email"],
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"==> Created superuser: {options['username']} / {options['password']}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("==> Setup complete!"))
