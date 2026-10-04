"""Kiểm thử: auth."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserProfile, UserSetting
from .signing import decrypt_value, encrypt_value
from .views import LoginPageView


class AuthPageTests(TestCase):
    def test_home_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_login_page(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_register_page(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)

    @override_settings(STATIC_URL="/static/")
    def test_home_page_has_static_links(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "/static/css/tokens-base.css")
        self.assertContains(response, "/static/css/responsive.css")


class AuthFlowTests(TestCase):
    def test_register_creates_user_and_redirects(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_invalid_rerenders(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "badpass",
                "password1": "StrongPass123!",
                "password2": "DifferentPass456!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "register")

    def test_login_and_logout(self):
        User.objects.create_user(username="logintest", password="secret123")
        response = self.client.post(
            reverse("login"),
            {
                "username": "logintest",
                "password": "secret123",
            },
        )
        self.assertEqual(response.status_code, 302)


class LoginRateLimitTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_lockout_after_repeated_failures(self):
        User.objects.create_user(username="lockme", password="secret123")
        for _ in range(LoginPageView.max_failed_attempts):
            self.client.post(
                reverse("login"),
                {"username": "lockme", "password": "wrong"},
            )
        # Đúng mật khẩu nhưng đã bị khoá → không đăng nhập được
        response = self.client.post(
            reverse("login"),
            {"username": "lockme", "password": "secret123"},
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertContains(response, "Quá nhiều lần đăng nhập sai")

    def test_success_clears_counter(self):
        User.objects.create_user(username="unlock", password="secret123")
        for _ in range(2):
            self.client.post(reverse("login"), {"username": "unlock", "password": "wrong"})
        response = self.client.post(
            reverse("login"), {"username": "unlock", "password": "secret123"}
        )
        self.assertEqual(response.status_code, 302)
        # Counter đã reset sau thành công
        response = self.client.post(reverse("login"), {"username": "unlock", "password": "wrong"})
        self.assertNotContains(response, "Quá nhiều lần đăng nhập sai")
        cache.clear()


class PasswordResetTests(TestCase):
    def test_reset_request_renders(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)

    def test_reset_flow_uses_email_templates(self):
        mail.outbox = []
        User.objects.create_user(
            username="resetuser", email="reset@example.com", password="OldPass123!"
        )
        response = self.client.post(
            reverse("password_reset"),
            {"email": "reset@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "summaries/password_reset_done.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset@example.com", mail.outbox[0].to)


class SettingsFlowTests(TestCase):
    def tearDown(self):
        cache.clear()

    def setUp(self):
        self.user = User.objects.create_user(username="settings-test", password="secret123")

    def test_settings_requires_login(self):
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 302)

    def test_settings_page_loads(self):
        self.client.login(username="settings-test", password="secret123")
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gemini")

    def test_settings_update_ratio(self):
        self.client.login(username="settings-test", password="secret123")
        self.client.post(
            reverse("settings"),
            {
                "default_summary_ratio": 0.7,
                "gemini_api_key": "",
            },
        )
        updated = UserSetting.objects.get(user=self.user)
        self.assertEqual(updated.default_summary_ratio, 0.7)

    def test_settings_save_and_clear_api_key(self):
        self.client.login(username="settings-test", password="secret123")
        self.client.post(
            reverse("settings"),
            {
                "default_summary_ratio": 0.2,
                "gemini_api_key": "my-key-123",
            },
        )
        stored = UserSetting.objects.get(user=self.user).gemini_api_key
        self.assertEqual(decrypt_value(stored), "my-key-123")
        self.client.post(
            reverse("settings"),
            {
                "default_summary_ratio": 0.2,
                "gemini_api_key": "",
                "clear_gemini_api_key": "on",
            },
        )
        self.assertEqual(UserSetting.objects.get(user=self.user).gemini_api_key, "")

    def test_settings_invalid_ratio_shows_error(self):
        self.client.login(username="settings-test", password="secret123")
        response = self.client.post(
            reverse("settings"),
            {
                "default_summary_ratio": 5.0,
                "gemini_api_key": "",
            },
        )
        self.assertContains(response, "value")


class SigningTests(TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        text = "my-api-key-123"
        self.assertEqual(decrypt_value(encrypt_value(text)), text)

    def test_encrypt_empty_returns_empty(self):
        self.assertEqual(encrypt_value(""), "")

    def test_decrypt_invalid_token_returns_raw(self):
        self.assertEqual(decrypt_value("not-a-valid-token"), "not-a-valid-token")


class SigningFallbackTests(TestCase):
    """Cover cryptography-not-installed fallback paths in signing.py."""

    def test_encrypt_when_fernet_none_returns_plaintext(self):
        import summaries.signing as signing

        real = signing.Fernet
        signing.Fernet = None
        try:
            self.assertEqual(encrypt_value("secret-value"), "secret-value")
        finally:
            signing.Fernet = real

    def test_decrypt_when_fernet_none_returns_raw(self):
        import summaries.signing as signing

        real = signing.Fernet
        signing.Fernet = None
        try:
            self.assertEqual(decrypt_value("raw-encrypted"), "raw-encrypted")
        finally:
            signing.Fernet = real

    def test_encrypt_when_fernet_none_and_empty_returns_empty(self):
        import summaries.signing as signing

        real = signing.Fernet
        signing.Fernet = None
        try:
            self.assertEqual(encrypt_value(""), "")
        finally:
            signing.Fernet = real

    def test_module_import_fallback_sets_none_on_missing_cryptography(self):
        import importlib

        import summaries.signing as signing

        real = signing.Fernet
        original_import = __import__

        def fake_import(name, *a, **k):
            if name.startswith("cryptography"):
                raise ImportError("blocked")
            return original_import(name, *a, **k)

        try:
            signing.Fernet = None
            with patch("builtins.__import__", side_effect=fake_import):
                importlib.reload(signing)
            self.assertIsNone(signing.Fernet)
        finally:
            signing.Fernet = real
            importlib.reload(signing)


class SuperuserRoleEvolutionTests(TestCase):
    def test_superuser_profile_becomes_admin_on_home_and_ratio_initialized(self):
        User.objects.create_superuser(username="boss", password="secret123")
        self.client.login(username="boss", password="secret123")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(user__username="boss")
        self.assertEqual(profile.role, "admin")
        setting = UserSetting.objects.get(user__username="boss")
        self.assertEqual(setting.default_summary_ratio, 0.2)
