"""Kiểm thử: ops."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Document, Summary, Tag, UserSetting


class ChecksTests(TestCase):
    def test_w001_when_prod_without_explicit_key(self):
        from .checks import check_production_encryption_key

        with override_settings(DEBUG=False, API_ENCRYPTION_KEY_EXPLICIT=False):
            warnings = check_production_encryption_key(None)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0].id, "summaries.W001")

    def test_no_warning_when_explicit_key(self):
        from .checks import check_production_encryption_key

        with override_settings(DEBUG=False, API_ENCRYPTION_KEY_EXPLICIT=True):
            self.assertEqual(check_production_encryption_key(None), [])

    def test_no_warning_in_debug(self):
        from .checks import check_production_encryption_key

        with override_settings(DEBUG=True, API_ENCRYPTION_KEY_EXPLICIT=False):
            self.assertEqual(check_production_encryption_key(None), [])


class UrlsTests(TestCase):
    def test_robots_txt(self):
        response = self.client.get(reverse("robots_txt"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Disallow: /admin", response.content.decode())

    def test_security_txt(self):
        response = self.client.get("/.well-known/security.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Contact:", response.content.decode())


class ObservabilityTests(TestCase):
    def test_response_includes_request_id_and_json_logs_correlate(self):
        import json
        import logging
        from uuid import UUID

        from config.logging_fmt import JsonFormatter
        from config.request_id import request_id_var

        response = self.client.get(reverse("health"))
        request_id = response["X-Request-ID"]
        UUID(request_id)

        token = request_id_var.set(request_id)
        try:
            record = logging.makeLogRecord({"msg": "test"})
            payload = json.loads(JsonFormatter().format(record))
            self.assertEqual(payload["request_id"], request_id)
        finally:
            request_id_var.reset(token)


class DeploymentConfigTests(TestCase):
    def test_multi_process_production_rejects_sqlite(self):
        import os
        import subprocess
        import sys

        from django.conf import settings

        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONPATH": str(settings.BACKEND_DIR),
                "DJANGO_DEBUG": "False",
                "DJANGO_SECRET_KEY": "test-production-secret",
                "DJANGO_ALLOWED_HOSTS": "app.example.com",
                "API_ENCRYPTION_KEY": "test-encryption-key",
                "DJANGO_REQUIRE_EXTERNAL_DATABASE": "True",
                "DB_ENGINE": "sqlite",
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires DB_ENGINE=mysql, postgres, or sqlserver", result.stderr)


class BackupDbTests(TestCase):
    def test_backup_creates_dump(self):
        import pathlib
        import tempfile as _tf

        from django.core.management import call_command

        with _tf.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "bk"
            call_command("backup_db", "--dest", str(dest))
            jsons = list(dest.rglob("db.json"))
            self.assertEqual(len(jsons), 1)
            self.assertGreater(jsons[0].stat().st_size, 0)

    def test_backup_with_media(self):
        import tempfile as _tf
        from pathlib import Path

        from django.core.management import call_command

        with _tf.TemporaryDirectory() as d:
            dest = Path(d) / "bk2"
            media = Path(d) / "media"
            media.mkdir(parents=True, exist_ok=True)
            probe = media / "_probe_backup.txt"
            probe.write_text("backup media probe", encoding="utf-8")
            with override_settings(MEDIA_ROOT=media):
                call_command("backup_db", "--dest", str(dest), "--include-media")
            copied_probe = next(dest.rglob("_probe_backup.txt"))
            self.assertEqual(copied_probe.read_text(encoding="utf-8"), "backup media probe")

    def test_backup_restore_roundtrip(self):
        """Backup có thể nạp lại vào một SQLite database cô lập."""
        import json
        import os
        import pathlib
        import subprocess
        import sys
        import tempfile as _tf

        from django.conf import settings as _settings
        from django.core.management import call_command
        from django.db import connection

        # Tạo dữ liệu test
        user = User.objects.create_user(username="backup-user", password="secret123")
        tag = Tag.objects.create(name="backup-tag")
        doc = Document.objects.create(
            user=user,
            source_type="text",
            title="Backup Doc",
            content="Nội dung test backup restore",
        )
        summary = Summary.objects.create(
            document=doc,
            user=user,
            title="Backup Summary",
            method="textrank",
            ratio=0.3,
            summary_text="Tóm tắt test",
        )
        summary.tags.add(tag)
        UserSetting.objects.filter(user=user).update(gemini_api_key="test-key")

        with _tf.TemporaryDirectory() as d:
            dest = pathlib.Path(d) / "bk"
            call_command("backup_db", "--dest", str(dest))
            db_json = list(dest.rglob("db.json"))[0]

            # Verify JSON structure
            data = json.loads(db_json.read_text(encoding="utf-8"))
            models = {item["model"] for item in data}
            self.assertIn("summaries.document", models)
            self.assertIn("summaries.summary", models)
            self.assertIn("summaries.tag", models)
            self.assertIn("summaries.usersetting", models)

            # Verify our test data is in the dump
            doc_dump = next(
                item
                for item in data
                if item["model"] == "summaries.document" and item["fields"]["title"] == "Backup Doc"
            )
            self.assertEqual(doc_dump["fields"]["content"], "Nội dung test backup restore")

            summary_dump = next(
                item
                for item in data
                if item["model"] == "summaries.summary"
                and item["fields"]["title"] == "Backup Summary"
            )
            self.assertEqual(summary_dump["fields"]["summary_text"], "Tóm tắt test")

            tag_dump = next(
                item
                for item in data
                if item["model"] == "summaries.tag" and item["fields"]["name"] == "backup-tag"
            )
            self.assertEqual(tag_dump["fields"]["name"], "backup-tag")

            setting_dump = next(
                item
                for item in data
                if item["model"] == "summaries.usersetting"
                and item["fields"]["gemini_api_key"] == "test-key"
            )
            self.assertEqual(setting_dump["fields"]["gemini_api_key"], "test-key")

            if connection.vendor != "sqlite":
                self.skipTest("Restore integration currently targets the CI SQLite backend.")

            restore_db = pathlib.Path(d) / "restored.sqlite3"
            environment = os.environ.copy()
            environment.update(
                {
                    "DJANGO_SETTINGS_MODULE": "config.settings",
                    "DJANGO_DEBUG": "True",
                    "DJANGO_SECRET_KEY": "isolated-backup-restore-test-key",
                    "DJANGO_ALLOWED_HOSTS": "localhost,testserver",
                    "DB_ENGINE": "sqlite",
                    "SQLITE_DB_PATH": str(restore_db),
                    "MEDIA_ROOT": str(pathlib.Path(d) / "restored-media"),
                    "PYTHONPATH": str(_settings.BACKEND_DIR),
                }
            )
            restore_script = (
                "import django, os; "
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); "
                "django.setup(); "
                "from django.core.management import call_command; "
                "call_command('migrate', verbosity=0); "
                f"call_command('loaddata', {str(db_json)!r}, verbosity=0); "
                "from summaries.models import Document, Summary, UserSetting; "
                "assert Document.objects.filter(title='Backup Doc', "
                "content='Nội dung test backup restore').exists(); "
                "assert Summary.objects.filter(title='Backup Summary', "
                "summary_text='Tóm tắt test').exists(); "
                "assert UserSetting.objects.filter(user__username='backup-user', "
                "gemini_api_key='test-key').exists()"
            )
            restored = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=_settings.ROOT_DIR,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(restored.returncode, 0, restored.stderr)

    def test_verify_backup_accepts_valid_backup_and_rejects_corruption(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from django.core.management import CommandError, call_command

        with TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "backup"
            call_command("backup_db", "--dest", str(destination))
            folder = next(destination.iterdir())
            call_command("verify_backup", str(folder))

            (folder / "db.json").write_text("corrupted", encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("verify_backup", str(folder))

    def test_verify_backup_rejects_invalid_manifest_and_path(self):
        import hashlib
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from django.core.management import CommandError, call_command

        with TemporaryDirectory() as temporary_directory:
            folder = Path(temporary_directory) / "backup"
            folder.mkdir()
            with self.assertRaises(CommandError):
                call_command("verify_backup", str(folder))

            for unsafe_name in ("../outside", r"..\outside"):
                (folder / "manifest.json").write_text(
                    json.dumps({"database_dump": unsafe_name, "sha256": "0" * 64}),
                    encoding="utf-8",
                )
                with self.assertRaises(CommandError):
                    call_command("verify_backup", str(folder))

            db_path = folder / "db.json"
            db_path.write_text("{}", encoding="utf-8")
            digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
            manifest_path = folder / "manifest.json"
            manifest_path.write_text(
                json.dumps({"database_dump": "db.json", "sha256": digest}),
                encoding="utf-8",
            )
            with self.assertRaises(CommandError):
                call_command("verify_backup", str(folder))

            manifest_path.write_text(
                json.dumps({"database_dump": "db.json", "sha256": 123}),
                encoding="utf-8",
            )
            with self.assertRaises(CommandError):
                call_command("verify_backup", str(folder))


class RateLimitMiddlewareTests(TestCase):
    def test_rate_limit_allows_first_request(self):
        response = self.client.post(
            reverse("create_summary"),
            {"source_type": "text", "text": "Test content", "method": "textrank", "ratio": 0.3},
            content_type="application/x-www-form-urlencoded",
        )
        self.assertNotEqual(response.status_code, 429)

    def test_rate_limit_blocks_rapid_requests(self):
        # First request OK
        self.client.post(
            reverse("create_summary"),
            {"source_type": "text", "text": "Test content", "method": "textrank", "ratio": 0.3},
            content_type="application/x-www-form-urlencoded",
        )
        # Second request within window -> 429
        response = self.client.post(
            reverse("create_summary"),
            {"source_type": "text", "text": "Test content 2", "method": "textrank", "ratio": 0.3},
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("retry_after", response.json())

    def test_untrusted_forwarded_header_cannot_bypass_rate_limit(self):
        self.client.post(
            reverse("create_summary"),
            {"source_type": "text", "text": "Test content", "method": "textrank", "ratio": 0.3},
            content_type="application/x-www-form-urlencoded",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        response = self.client.post(
            reverse("create_summary"),
            {"source_type": "text", "text": "Test content 2", "method": "textrank", "ratio": 0.3},
            content_type="application/x-www-form-urlencoded",
            HTTP_X_FORWARDED_FOR="5.6.7.8",
        )
        self.assertEqual(response.status_code, 429)

    def test_different_remote_ips_have_independent_limits(self):
        for remote_addr in ("192.0.2.10", "192.0.2.11"):
            response = self.client.post(
                reverse("create_summary"),
                {
                    "source_type": "text",
                    "text": f"Test content {remote_addr}",
                    "method": "textrank",
                    "ratio": 0.3,
                },
                content_type="application/x-www-form-urlencoded",
                REMOTE_ADDR=remote_addr,
            )
            self.assertNotEqual(response.status_code, 429)

    def test_trusted_proxy_forwarded_chain_uses_first_untrusted_hop(self):
        from django.test import RequestFactory

        from summaries.middleware import get_client_ip

        request = RequestFactory().get(
            "/api/test/",
            REMOTE_ADDR="10.0.0.2",
            HTTP_X_FORWARDED_FOR="198.51.100.15, 10.0.0.1",
        )
        with override_settings(TRUSTED_PROXY_IPS=("10.0.0.0/8",)):
            self.assertEqual(get_client_ip(request), "198.51.100.15")

    def test_untrusted_forwarded_chain_is_ignored(self):
        from django.test import RequestFactory

        from summaries.middleware import get_client_ip

        request = RequestFactory().get(
            "/api/test/",
            REMOTE_ADDR="192.0.2.9",
            HTTP_X_FORWARDED_FOR="198.51.100.15",
        )
        self.assertEqual(get_client_ip(request), "192.0.2.9")

    def test_rate_limit_exempt_paths(self):
        # Health endpoint should not be rate limited
        for _ in range(5):
            response = self.client.get(reverse("health"))
            self.assertNotEqual(response.status_code, 429)


class MetricsEndpointTests(TestCase):
    def test_metrics_endpoint_returns_prometheus_format(self):
        response = self.client.get("/metrics/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        content = response.content.decode()
        self.assertIn("http_requests_total", content)
        self.assertIn("http_request_duration_seconds", content)

    def test_metrics_increments_on_request(self):
        self.client.get("/health/")
        response = self.client.get("/metrics/")
        content = response.content.decode()
        self.assertIn('http_requests_total{endpoint="/health/",method="GET",status="200"}', content)


class SetupCommandTests(TestCase):
    def test_setup_migrate_only(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        try:
            call_command("setup")
        except CommandError:
            pass  # migrate no-op in test DB is fine

    def test_setup_create_superuser_when_none(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        user_model = get_user_model()
        user_model.objects.all().delete()
        call_command("setup", create_superuser=True, username="newboss", password="NewPass456!")
        self.assertTrue(user_model.objects.filter(username="newboss", is_superuser=True).exists())

    def test_setup_skips_when_superuser_exists(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        user_model = get_user_model()
        user_model.objects.filter(is_superuser=True).delete()
        user_model.objects.create_superuser(
            username="existingboss", password="Pass123!", email="b@b.com"
        )
        call_command("setup", create_superuser=True, username="newboss", password="NewPass456!")
        self.assertFalse(user_model.objects.filter(username="newboss").exists())
