"""Kiểm thử: pages."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import path, reverse

from .models import Document, Summary
from .views import LoginPageView as _Login
from .views import RegisterPageView as _Register
from .views import home as _home


def _boom_view(_request):  # noqa: N802
    raise RuntimeError("boom")


# ROOT_URLCONF nhỏ, chỉ dùng riêng cho ErrorPageTests
urlpatterns = [
    path("", _home, name="home"),
    path("login/", _Login.as_view(), name="login"),
    path("register/", _Register.as_view(), name="register"),
    path("__boom__/", _boom_view),
]


class AdminPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="superadmin",
            password="secret123",
        )

    def test_admin_login_required(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)

    def test_admin_index_loads(self):
        self.client.login(username="superadmin", password="secret123")
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)

    def test_admin_summary_list_loads(self):
        self.client.login(username="superadmin", password="secret123")
        response = self.client.get(reverse("admin:summaries_summary_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_admin_document_list_loads(self):
        self.client.login(username="superadmin", password="secret123")
        response = self.client.get(reverse("admin:summaries_document_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_admin_userprofile_list_loads(self):
        self.client.login(username="superadmin", password="secret123")
        response = self.client.get(reverse("admin:summaries_userprofile_changelist"))
        self.assertEqual(response.status_code, 200)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["*"])
class ErrorPageTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False

    def test_missing_page_renders_custom_404(self):
        response = self.client.get("/nonexistent-page/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Trang bạn tìm kiếm không tồn tại.", response.content.decode())
        self.assertIn("error-code", response.content.decode())

    def test_server_error_renders_custom_500(self):
        with override_settings(ROOT_URLCONF="summaries.test_pages"):
            response = self.client.get("/__boom__/")
        self.assertEqual(response.status_code, 500)
        content = response.content.decode()
        self.assertIn("Lỗi máy chủ", content)
        self.assertIn("Vui lòng thử lại sau", content)


class SecurityHeaderTests(TestCase):
    def test_csp_policy_present_on_all_pages(self):
        response = self.client.get(reverse("home"))
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self' 'nonce-", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertIn("img-src 'self' data:", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_clickjacking_protection_enabled(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

    def test_nosniff_header(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_referrer_policy(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_csrf_blocks_missing_token(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("login"), {"username": "nobody", "password": "x"})
        self.assertEqual(response.status_code, 403)


class SharingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="share-tester", password="secret123")
        self.document = Document.objects.create(
            user=self.user, source_type="text", title="Tài liệu chia sẻ", content="Nội dung"
        )
        self.summary = Summary.objects.create(
            document=self.document,
            user=self.user,
            title="Tóm tắt chia sẻ",
            summary_text="Nội dung tóm tắt",
        )

    def test_generated_share_link_opens_public_summary(self):
        from .sharing import generate_share_token

        token = generate_share_token(self.summary)

        response = self.client.get(reverse("shared_summary", kwargs={"token": token}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nội dung tóm tắt")


class HealthCheckTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "ok", "media": "ok"},
        )


class HealthDegradedTests(TestCase):
    def test_health_degraded_on_db_error(self):
        from unittest.mock import patch

        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("db down")
            response = self.client.get(reverse("health"))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["status"], "degraded")
            self.assertEqual(response.json()["database"], "error")
            self.assertNotIn("db down", response.content.decode())

    def test_health_degraded_on_media_error(self):
        with patch("pathlib.Path.unlink", side_effect=OSError("locked")):
            response = self.client.get(reverse("health"))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["media"], "error")
            self.assertNotIn("locked", response.content.decode())

    def test_home_gemini_toggle(self):

        # Không có key hệ thống → gemini_available False cho anon
        with override_settings(GEMINI_API_KEY=""):
            response = self.client.get(reverse("home"))
            self.assertEqual(response.status_code, 200)
            # Trang vẫn render, button gemini ở dạng disabled
            self.assertContains(response, "Gemini AI")

    def test_home_gemini_available_with_system_key(self):
        from .views import home_gemini_available

        with override_settings(GEMINI_API_KEY="test-key"):
            self.assertTrue(home_gemini_available(None))

    def test_home_gemini_available_with_user_key(self):
        from .views import home_gemini_available

        user = User.objects.create_user(username="gemini-user", password="secret123")
        # post_save signal đã auto-create UserSetting
        user.setting.gemini_api_key = "user-key"
        user.setting.save()
        with override_settings(GEMINI_API_KEY=""):
            self.assertTrue(home_gemini_available(user))


class APIDocsTests(TestCase):
    def test_schema_endpoint(self):
        import json

        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("openapi", data)
        self.assertIn("info", data)
        self.assertEqual(data["info"]["title"], "SummarEase API")

    def test_swagger_ui_endpoint(self):
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("swagger-ui", response.content.decode())

    def test_redoc_endpoint(self):
        response = self.client.get("/api/redoc/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("<redoc", response.content.decode())
