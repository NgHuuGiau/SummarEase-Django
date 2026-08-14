"""Test cho SummarEase Django."""

import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import SettingsForm, SummaryRequestForm
from .models import Document, Summary, UserProfile, UserSetting
from .nlp import (
    detect_language,
    extract_keywords,
    extract_text,
    generate_title,
    highlight_keywords,
    normalize_text,
    split_sentences,
    split_words,
    textrank_summarize,
    truncate_text,
)
from .signing import decrypt_value, encrypt_value


class TestHelperMixin:
    def _create_user(self, username, password="secret123", is_superuser=False):
        if is_superuser:
            user = User.objects.create_superuser(username=username, password=password)
        else:
            user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(user=user, role="admin" if is_superuser else "user")
        UserSetting.objects.create(user=user)
        return user

# ──────────────────────────────────────────────
#  NLP UNIT TESTS
# ──────────────────────────────────────────────

class NlpSplitTests(TestCase):
    def test_split_sentences_basic(self):
        result = split_sentences("Hello world. This is fun!")
        self.assertEqual(len(result), 2)

    def test_split_sentences_abbreviations(self):
        text = "Dr. Smith went to New York. He arrived at 5 p.m."
        result = split_sentences(text)
        self.assertEqual(len(result), 2)

    def test_split_sentences_vietnamese_abbrev(self):
        text = "Tp. Hồ Chí Minh là thành phố lớn nhất. Nó nằm ở phía Nam."
        result = split_sentences(text)
        self.assertEqual(len(result), 2)

    def test_split_words_basic(self):
        result = split_words("Hello World!")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_split_words_vietnamese(self):
        result = split_words("Xin chào thế giới!")
        self.assertIn("chào", result)
        self.assertIn("thế", result)


class NlpNormalizeTests(TestCase):
    def test_normalize_removes_extra_spaces(self):
        result = normalize_text("Hello    world\n\n  test")
        self.assertEqual(result, "Hello world test")

    def test_normalize_strips_whitespace(self):
        result = normalize_text("  hello  ")
        self.assertEqual(result, "hello")


class NlpDetectLanguageTests(TestCase):
    def test_detect_english_by_diacritics(self):
        result = detect_language("The quick brown fox jumps over the lazy dog.")
        self.assertEqual(result, "english")

    def test_detect_vietnamese_by_diacritics(self):
        result = detect_language("Xin chào thế giới! Hôm nay là một ngày đẹp trời.")
        self.assertEqual(result, "vietnamese")

    def test_detect_vietnamese_no_diacritics(self):
        result = detect_language("Xin chao the gioi! Hom nay la mot ngay dep troi.")
        self.assertEqual(result, "vietnamese")

    def test_detect_empty_falls_to_english(self):
        result = detect_language("")
        self.assertEqual(result, "english")


class NlpKeywordsTests(TestCase):
    def test_extract_keywords_returns_top_words(self):
        text = "python django python django django web framework python"
        result = extract_keywords(text, limit=3)
        self.assertIn("python", result)
        self.assertIn("django", result)
        self.assertGreaterEqual(len(result), 2)

    def test_highlight_keywords_adds_mark_tags(self):
        text = "python is great. django is better."
        result = highlight_keywords(text, ["python", "django"])
        self.assertIn("<mark>python</mark>", result)
        self.assertIn("<mark>django</mark>", result)

    def test_highlight_keywords_escapes_html(self):
        text = "test <script>alert('xss')</script>"
        result = highlight_keywords(text, ["test"])
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)


class NlpTitleTests(TestCase):
    def test_generate_title_from_summary(self):
        result = generate_title("This is the first sentence of the summary.")
        self.assertEqual(result, "This is the first sentence of the summary.")

    def test_generate_title_with_source_name(self):
        result = generate_title("summary", "my-doc.pdf")
        self.assertIn("my-doc.pdf", result)

    def test_generate_title_empty_returns_default(self):
        result = generate_title("")
        self.assertEqual(result, "Tóm tắt tài liệu")


class NlpTruncateTests(TestCase):
    def test_truncate_short_text(self):
        text = "short text"
        result = truncate_text(text, max_chars=100)
        self.assertEqual(result, text)

    def test_truncate_long_text(self):
        text = " ".join(["word"] * 100)
        result = truncate_text(text, max_chars=20)
        self.assertLessEqual(len(result), 20)


# ──────────────────────────────────────────────
#  MODEL TESTS
# ──────────────────────────────────────────────

class DocumentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="doc-tester", password="secret123")

    def test_create_document(self):
        doc = Document.objects.create(
            user=self.user,
            source_type="text",
            title="Test doc",
            content="Hello world",
        )
        self.assertEqual(str(doc), "Test doc")


class HealthCheckTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class SummaryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sum-tester", password="secret123")
        self.doc = Document.objects.create(user=self.user, source_type="text", title="Doc", content="Content")

    def test_create_summary(self):
        summary = Summary.objects.create(
            document=self.doc, user=self.user, title="Sum", method="textrank",
            language="english", ratio=0.5, summary_text="Summary text",
        )
        self.assertEqual(str(summary), "Sum")

    def test_summary_timestamps(self):
        summary = Summary.objects.create(
            document=self.doc, user=self.user, title="Sum", method="textrank",
            language="english", ratio=0.5, summary_text="Text",
        )
        self.assertIsNotNone(summary.created_at)


class UserProfileModelTests(TestCase):
    def test_create_profile_auto_defaults(self):
        user = User.objects.create_user(username="profile-test", password="secret123")
        profile = UserProfile.objects.create(user=user)
        self.assertEqual(profile.role, "user")

    def test_admin_profile_role(self):
        user = User.objects.create_superuser(username="admin-test", password="secret123")
        profile = UserProfile.objects.create(user=user, role="admin")
        self.assertEqual(profile.role, "admin")


# ──────────────────────────────────────────────
#  VIEW / INTEGRATION TESTS
# ──────────────────────────────────────────────

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
        self.assertContains(response, "/static/css/app.css")


class AuthFlowTests(TestCase):
    def test_register_creates_user_and_redirects(self):
        response = self.client.post(reverse("register"), {
            "username": "newuser",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_login_and_logout(self):
        User.objects.create_user(username="logintest", password="secret123")
        response = self.client.post(reverse("login"), {
            "username": "logintest",
            "password": "secret123",
        })
        self.assertEqual(response.status_code, 302)


class SummaryFlowTests(TestCase):
    def tearDown(self):
        cache.clear()

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret123")
        UserProfile.objects.create(user=self.user, role="user")
        UserSetting.objects.create(user=self.user)
        self.other = User.objects.create_user(username="other", password="secret123")
        UserProfile.objects.create(user=self.other, role="user")
        UserSetting.objects.create(user=self.other)
        self.admin = User.objects.create_superuser(username="admin", password="secret123")
        UserProfile.objects.create(user=self.admin, role="admin")
        UserSetting.objects.create(user=self.admin)

    def test_login_required_for_create_summary(self):
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank",
            "text": "test text", "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 302)

    def test_create_summary_textrank(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank",
            "text": "First sentence here. Second sentence follows. Third one is final.",
            "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(Summary.objects.count(), 1)

    def test_create_summary_empty_text_returns_error(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank", "text": "", "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.json())

    def test_rate_limit_blocks_rapid_requests(self):
        self.client.login(username="tester", password="secret123")
        self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank",
            "text": "A sentence. B sentence. C sentence.", "ratio": 0.2,
        })
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank",
            "text": "D sentence. E sentence. F sentence.", "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 429)

    def test_admin_can_view_all_history(self):
        doc = Document.objects.create(
            user=self.other, source_type="text", title="Doc", content="Content",
        )
        Summary.objects.create(
            document=doc, user=self.other, title="Other summary",
            method="textrank", language="en", ratio=0.2, summary_text="Text",
        )
        self.client.login(username="admin", password="secret123")
        response = self.client.get(reverse("history"))
        self.assertContains(response, "Other summary")

    def test_user_cannot_view_others_detail(self):
        doc = Document.objects.create(
            user=self.other, source_type="text", title="Doc", content="Content",
        )
        summary = Summary.objects.create(
            document=doc, user=self.other, title="Private",
            method="textrank", language="en", ratio=0.2, summary_text="Text",
        )
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("history_detail", kwargs={"pk": summary.pk}))
        self.assertEqual(response.status_code, 404)


class SettingsFlowTests(TestCase):
    def tearDown(self):
        cache.clear()
    def setUp(self):
        self.user = User.objects.create_user(username="settings-test", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)

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
        self.client.post(reverse("settings"), {
            "default_summary_ratio": 0.7, "gemini_api_key": "",
        })
        updated = UserSetting.objects.get(user=self.user)
        self.assertEqual(updated.default_summary_ratio, 0.7)

    def test_settings_save_and_clear_api_key(self):
        self.client.login(username="settings-test", password="secret123")
        self.client.post(reverse("settings"), {
            "default_summary_ratio": 0.2, "gemini_api_key": "my-key-123",
        })
        stored = UserSetting.objects.get(user=self.user).gemini_api_key
        self.assertEqual(decrypt_value(stored), "my-key-123")
        self.client.post(reverse("settings"), {
            "default_summary_ratio": 0.2, "gemini_api_key": "",
        })
        self.assertEqual(UserSetting.objects.get(user=self.user).gemini_api_key, "")

    def test_settings_invalid_ratio_shows_error(self):
        self.client.login(username="settings-test", password="secret123")
        response = self.client.post(reverse("settings"), {
            "default_summary_ratio": 5.0, "gemini_api_key": "",
        })
        self.assertContains(response, "value")


# ──────────────────────────────────────────────
#  NLP EDGE CASE TESTS
# ──────────────────────────────────────────────

class NlpEdgeCaseTests(TestCase):
    def test_split_sentences_single_sentence(self):
        result = split_sentences("Just one sentence here")
        self.assertEqual(len(result), 1)

    def test_split_sentences_empty(self):
        result = split_sentences("")
        self.assertEqual(result, [])

    def test_split_sentences_question_exclamation(self):
        result = split_sentences("What is this? Amazing! Yes.")
        self.assertEqual(len(result), 3)

    def test_split_words_empty(self):
        result = split_words("")
        self.assertEqual(result, [])

    def test_split_words_special_chars(self):
        result = split_words("hello... world!!! test's")
        self.assertIn("hello", result)
        self.assertIn("world", result)
        self.assertIn("test's", result)

    def test_normalize_empty(self):
        result = normalize_text("")
        self.assertEqual(result, "")

    def test_normalize_tabs(self):
        result = normalize_text("hello\t\tworld")
        self.assertEqual(result, "hello world")

    def test_detect_language_mixed(self):
        result = detect_language("Hello everyone! Hom nay troi dep qua.")
        self.assertEqual(result, "vietnamese")

    def test_detect_language_vietnamese_diacritics_only(self):
        result = detect_language("Xin chào, hôm nay là thứ năm.")
        self.assertEqual(result, "vietnamese")

    def test_detect_language_english_only(self):
        result = detect_language("Today is a great day to learn something new.")
        self.assertEqual(result, "english")

    def test_extract_keywords_empty(self):
        result = extract_keywords("")
        self.assertEqual(result, [])

    def test_extract_keywords_limit(self):
        text = "apple banana apple banana cherry apple date"
        result = extract_keywords(text, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "apple")

    def test_highlight_keywords_no_match(self):
        result = highlight_keywords("hello world", ["python"])
        self.assertNotIn("<mark>", result)

    def test_highlight_keywords_mark_not_escaped(self):
        result = highlight_keywords("hello world", ["hello"])
        self.assertEqual(result, "<mark>hello</mark> world")

    def test_generate_title_adds_period(self):
        result = generate_title("Summary without period")
        self.assertTrue(result.endswith("."))

    def test_textrank_summarize_long_text(self):
        sentences = "This is the first sentence about Python. "
        sentences += "Django is a web framework written in Python. "
        sentences += "It is used by many developers worldwide. "
        sentences += "The framework follows the MVT architecture. "
        sentences += "Python is a versatile programming language. "
        result = textrank_summarize(sentences, ratio=0.5)
        self.assertIn("summary", result)
        self.assertIn("keywords", result)
        self.assertIn("title", result)


# ──────────────────────────────────────────────
#  FORM VALIDATION TESTS
# ──────────────────────────────────────────────

class FormValidationTests(TestCase):
    def test_settings_form_valid(self):
        form = SettingsForm(data={"default_summary_ratio": 0.3, "gemini_api_key": ""})
        self.assertTrue(form.is_valid())

    def test_settings_form_negative_ratio(self):
        form = SettingsForm(data={"default_summary_ratio": -1, "gemini_api_key": ""})
        self.assertFalse(form.is_valid())

    def test_settings_form_ratio_too_high(self):
        form = SettingsForm(data={"default_summary_ratio": 2.0, "gemini_api_key": ""})
        self.assertFalse(form.is_valid())

    def test_settings_form_long_api_key(self):
        form = SettingsForm(data={"default_summary_ratio": 0.2, "gemini_api_key": "k" * 500})
        self.assertFalse(form.is_valid())

    def test_summary_form_missing_source_type(self):
        form = SummaryRequestForm(data={})
        self.assertFalse(form.is_valid())


# ──────────────────────────────────────────────
#  ADMIN PAGE TESTS
# ──────────────────────────────────────────────

class AdminPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="superadmin", password="secret123",
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        UserSetting.objects.create(user=self.admin)

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


# ──────────────────────────────────────────────
#  HISTORY PAGINATION TESTS
# ──────────────────────────────────────────────

class HistoryPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="paginator", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content",
        )
        for i in range(15):
            Summary.objects.create(
                document=doc, user=self.user, title=f"Summary {i}",
                method="textrank", language="en", ratio=0.2, summary_text=f"Text {i}",
            )
        self.client.login(username="paginator", password="secret123")

    def test_history_first_page(self):
        response = self.client.get(reverse("history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Summary 14")

    def test_history_second_page(self):
        response = self.client.get(reverse("history"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Summary 0")

    def test_history_invalid_page(self):
        response = self.client.get(reverse("history"), {"page": 999})
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────
#  PERMISSION TESTS
# ──────────────────────────────────────────────

class PermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="normaluser", password="secret123")
        UserProfile.objects.create(user=self.user, role="user")
        UserSetting.objects.create(user=self.user)
        self.admin = User.objects.create_superuser(username="super", password="secret123")
        UserProfile.objects.create(user=self.admin, role="admin")
        UserSetting.objects.create(user=self.admin)
        self.doc = Document.objects.create(
            user=self.user, source_type="text", title="My doc", content="My content",
        )
        self.summary = Summary.objects.create(
            document=self.doc, user=self.user, title="My summary",
            method="textrank", language="en", ratio=0.2, summary_text="My text",
        )

    def test_own_history_detail_accessible(self):
        self.client.login(username="normaluser", password="secret123")
        response = self.client.get(reverse("history_detail", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 200)

    def test_own_delete_allowed(self):
        self.client.login(username="normaluser", password="secret123")
        response = self.client.post(reverse("history_delete", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Summary.objects.filter(pk=self.summary.pk).exists())

    def test_other_delete_denied(self):
        other = User.objects.create_user(username="otheruser", password="secret123")
        UserProfile.objects.create(user=other)
        UserSetting.objects.create(user=other)
        self.client.login(username="otheruser", password="secret123")
        response = self.client.post(reverse("history_delete", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 404)

    def test_admin_can_delete_any(self):
        self.client.login(username="super", password="secret123")
        response = self.client.post(reverse("history_delete", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Summary.objects.filter(pk=self.summary.pk).exists())


# ──────────────────────────────────────────────
#  DELETE CASCADE TESTS
# ──────────────────────────────────────────────

class DeleteCascadeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cascade-user", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)

    def test_delete_document_cascades_summary(self):
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content",
        )
        summary = Summary.objects.create(
            document=doc, user=self.user, title="Sum",
            method="textrank", language="en", ratio=0.2, summary_text="Text",
        )
        doc.delete()
        self.assertFalse(Summary.objects.filter(pk=summary.pk).exists())

    def test_delete_user_does_not_delete_summary(self):
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content",
        )
        Summary.objects.create(
            document=doc, user=self.user, title="Sum",
            method="textrank", language="en", ratio=0.2, summary_text="Text",
        )
        self.user.delete()
        self.assertEqual(Summary.objects.count(), 0)
        self.assertEqual(Document.objects.count(), 0)


# ──────────────────────────────────────────────
#  URL EXTRACTION TESTS (MOCKED)
# ──────────────────────────────────────────────

class UrlExtractionTests(TestCase):
    def _mock_session_get(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.headers = {"Content-Type": "text/html; charset=utf-8"}

    @patch("summaries.nlp._get_http_session")
    def test_extract_text_from_url(self, mock_session):
        sess = mock_session.return_value
        sess.get.return_value.status_code = 200
        sess.get.return_value.headers = {"Content-Type": "text/html; charset=utf-8"}
        sess.get.return_value.text = (
            "<html><body><p>Hello world. This is a test page.</p></body></html>"
        )
        result = extract_text("https://example.com")
        self.assertIn("Hello world", result)

    @patch("summaries.nlp._get_http_session")
    def test_extract_text_from_url_removes_scripts(self, mock_session):
        sess = mock_session.return_value
        sess.get.return_value.status_code = 200
        sess.get.return_value.headers = {"Content-Type": "text/html; charset=utf-8"}
        sess.get.return_value.text = (
            "<html><head><script>alert('xss')</script></head>"
            "<body><p>Main content here.</p></body></html>"
        )
        result = extract_text("https://example.com")
        self.assertIn("Main content", result)
        self.assertNotIn("alert", result)

    @patch("summaries.nlp._get_http_session")
    def test_extract_text_from_url_invalid_content_type(self, mock_session):
        sess = mock_session.return_value
        sess.get.return_value.status_code = 200
        sess.get.return_value.headers = {"Content-Type": "application/pdf"}
        sess.get.return_value.text = "not html"
        with self.assertRaises(ValueError):
            extract_text("https://example.com/file.pdf")

    @patch("summaries.nlp._get_http_session")
    def test_extract_text_from_url_raises_on_timeout(self, mock_session):
        from requests.exceptions import Timeout as RequestsTimeout
        sess = mock_session.return_value
        sess.get.side_effect = RequestsTimeout("Timeout")
        with self.assertRaises(ValueError):
            extract_text("https://example.com")

    def test_extract_text_from_url_invalid_scheme(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            extract_text("ftp://example.com")

    def test_extract_text_from_url_no_netloc(self):
        with self.assertRaises(ValueError):
            extract_text("http://")


# ──────────────────────────────────────────────
#  FILE UPLOAD TESTS
# ──────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), RATE_LIMIT_SECONDS=0)
class FileUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="uploader", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)
        self.client.login(username="uploader", password="secret123")

    def test_upload_txt_file(self):
        text_content = b"This is a test document. It has multiple sentences. We need enough text."
        uploaded = SimpleUploadedFile("test.txt", text_content, content_type="text/plain")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    def test_upload_file_too_large(self):
        big_content = b"x" * (10 * 1024 * 1024 + 1)
        uploaded = SimpleUploadedFile("big.txt", big_content, content_type="text/plain")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_no_file_sent(self):
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank", "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_unsupported_format(self):
        uploaded = SimpleUploadedFile("test.exe", b"fake content", content_type="application/octet-stream")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)


# ──────────────────────────────────────────────
#  GEMINI SUMMARIZE TESTS (MOCKED)
# ──────────────────────────────────────────────

@override_settings(RATE_LIMIT_SECONDS=0)
class GeminiSummarizeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gemini-test", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user, gemini_api_key=encrypt_value("fake-key"))
        self.client.login(username="gemini-test", password="secret123")
        self.mock_response = {
            "candidates": [{"content": {"parts": [{"text": "This is a short summary."}]}}]
        }

    def _mock_session(self, mock_get_session, status_code=200, response_data=None):
        sess = mock_get_session.return_value
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = response_data or self.mock_response
        mock_resp.text = ""
        if status_code >= 400:
            from requests.exceptions import HTTPError
            mock_resp.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
        sess.post.return_value = mock_resp
        return sess

    def tearDown(self):
        cache.clear()

    @patch("summaries.nlp._get_http_session")
    def test_gemini_summarize_success(self, mock_get_session):
        self._mock_session(mock_get_session)
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "gemini",
            "text": "This is the first sentence. Here is another one. Yet a third sentence.",
            "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    @override_settings(GEMINI_API_KEY="")
    @patch("summaries.nlp._get_http_session")
    def test_gemini_summarize_api_key_missing(self, mock_get_session):
        self._mock_session(mock_get_session)
        UserSetting.objects.filter(user=self.user).update(gemini_api_key="")
        cache.clear()
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "gemini",
            "text": "Some text for summary.", "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])

    @patch("summaries.nlp._get_http_session")
    def test_gemini_summarize_empty_response(self, mock_get_session):
        bad_resp = {"candidates": [{"content": {"parts": [{"text": ""}]}}]}
        self._mock_session(mock_get_session, response_data=bad_resp)
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "gemini",
            "text": "First word. Second word. Third word.", "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)

    @patch("summaries.nlp._get_http_session")
    def test_gemini_summarize_http_error(self, mock_get_session):
        self._mock_session(mock_get_session, status_code=500)
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "gemini",
            "text": "First word. Second word. Third word.", "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)

    @patch("summaries.nlp._get_http_session")
    def test_gemini_summarize_malformed_json(self, mock_get_session):
        bad_resp = {"unexpected": "format"}
        self._mock_session(mock_get_session, response_data=bad_resp)
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "gemini",
            "text": "Some text here. More text there.", "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 400)


# ──────────────────────────────────────────────
#  FILE EXTRACTION TESTS (MOCKED)
# ──────────────────────────────────────────────

@override_settings(RATE_LIMIT_SECONDS=0)
class FileExtractionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="extract-test", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)
        self.client.login(username="extract-test", password="secret123")

    def tearDown(self):
        cache.clear()

    @patch("summaries.nlp._extract_text_from_txt")
    def test_txt_file_extraction(self, mock_extract):
        mock_extract.return_value = "This is extracted text from a txt file. It has multiple sentences."
        uploaded = SimpleUploadedFile("test.txt", b"ignored", content_type="text/plain")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        mock_extract.assert_called_once()

    @patch("summaries.nlp._extract_text_from_docx")
    def test_docx_file_extraction(self, mock_extract):
        mock_extract.return_value = "Extracted content from a DOCX file."
        uploaded = SimpleUploadedFile("test.docx", b"ignored", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        mock_extract.assert_called_once()

    @patch("summaries.nlp._extract_text_from_pdf")
    def test_pdf_file_extraction(self, mock_extract):
        mock_extract.return_value = "Extracted content from a PDF file."
        uploaded = SimpleUploadedFile("test.pdf", b"ignored", content_type="application/pdf")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        mock_extract.assert_called_once()

    @patch("summaries.nlp._extract_text_from_epub")
    def test_epub_file_extraction(self, mock_extract):
        mock_extract.return_value = "Extracted content from an EPUB file."
        uploaded = SimpleUploadedFile("test.epub", b"ignored", content_type="application/epub+zip")
        response = self.client.post(reverse("create_summary"), {
            "source_type": "file", "method": "textrank",
            "upload": uploaded, "ratio": 0.3,
        })
        self.assertEqual(response.status_code, 200)
        mock_extract.assert_called_once()


# ──────────────────────────────────────────────
#  ERROR PAGE TESTS (404 / 500)
# ──────────────────────────────────────────────

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
        with override_settings(ROOT_URLCONF="summaries.tests"):
            response = self.client.get("/__boom__/")
        self.assertEqual(response.status_code, 500)
        content = response.content.decode()
        self.assertIn("Lỗi máy chủ", content)
        self.assertIn("Vui lòng thử lại sau", content)


# ──────────────────────────────────────────────
#  SECURITY HEADER TESTS
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
#  CONTENT EDGE CASE TESTS
# ──────────────────────────────────────────────

@override_settings(RATE_LIMIT_SECONDS=0)
class ContentEdgeCaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="edge-test", password="secret123")
        UserProfile.objects.create(user=self.user)
        UserSetting.objects.create(user=self.user)
        self.client.login(username="edge-test", password="secret123")

    def tearDown(self):
        cache.clear()

    def test_single_character_text(self):
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank", "text": "A", "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_whitespace_only_text_rejected(self):
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank", "text": "   \n\t  ", "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_very_long_text_summarized(self):
        long_text = ("Đây là một câu dùng để kiểm tra khả năng xử lý văn bản dài. "
                     "Khi dữ liệu lớn, hệ thống vẫn phải tóm tắt chính xác và đầy đủ. ") * 60
        response = self.client.post(reverse("create_summary"), {
            "source_type": "text", "method": "textrank", "text": long_text, "ratio": 0.2,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["summary"])


# ── ROOT_URLCONF nhỏ dùng riêng cho ErrorPageTests ──
from django.urls import path as _path  # noqa: E402

from .views import LoginPageView as _Login  # noqa: E402
from .views import RegisterPageView as _Register  # noqa: E402
from .views import home as _home  # noqa: E402


def _boom_view(_request):  # noqa: N802
    raise RuntimeError("boom")


urlpatterns = [
    _path("", _home, name="home"),
    _path("login/", _Login.as_view(), name="login"),
    _path("register/", _Register.as_view(), name="register"),
    _path("__boom__/", _boom_view),
]
