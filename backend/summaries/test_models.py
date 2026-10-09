"""Kiểm thử: models."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Document, Summary, Tag, UserProfile, UserSetting


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

    def test_tag_str_returns_name(self):
        tag = Tag.objects.create(name="Chatbot")
        self.assertEqual(str(tag), "Chatbot")


class SummaryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sum-tester", password="secret123")
        self.other = User.objects.create_user(username="other-tester", password="secret123")
        self.doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content"
        )

    def test_create_summary(self):
        summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Sum",
            method="textrank",
            language="english",
            ratio=0.5,
            summary_text="Summary text",
        )
        self.assertEqual(str(summary), "Sum")

    def test_summary_timestamps(self):
        summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Sum",
            method="textrank",
            language="english",
            ratio=0.5,
            summary_text="Text",
        )
        self.assertIsNotNone(summary.created_at)

    def test_search_falls_back_to_icontains_when_postgres_search_disabled(self):
        summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Tóm tắt kiểm thử",
            summary_text="Nội dung tìm kiếm mẫu",
        )

        results = Summary.search(self.user, "tìm kiếm")

        self.assertEqual(list(results), [summary])

    def test_search_is_scoped_to_user(self):
        mine = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Tóm tắt riêng",
            summary_text="Nội dung chung",
        )
        theirs = Summary.objects.create(
            document=self.doc,
            user=self.other,
            title="Tóm tắt người khác",
            summary_text="Nội dung chung",
        )

        results = Summary.search(self.user, "chung")

        self.assertIn(mine, results)
        self.assertNotIn(theirs, results)


class UserProfileModelTests(TestCase):
    def test_create_profile_auto_defaults(self):
        user = User.objects.create_user(username="profile-test", password="secret123")
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, "user")

    def test_admin_profile_role(self):
        user = User.objects.create_superuser(username="admin-test", password="secret123")
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, "admin")


class ModelStrAndCleanupTests(TestCase):
    def test_cleanup_uploaded_file_empty(self):
        from .models import _cleanup_uploaded_file

        _cleanup_uploaded_file("")
        _cleanup_uploaded_file(None)

    def test_cleanup_uploaded_file_removes_existing(self):
        import pathlib
        import tempfile as _tf

        from .models import _cleanup_uploaded_file

        with _tf.TemporaryDirectory() as d:
            target = pathlib.Path(d) / "x.txt"
            target.write_text("hi", encoding="utf-8")
            with override_settings(MEDIA_ROOT=d):
                _cleanup_uploaded_file("x.txt")
            self.assertFalse(target.exists())

    def test_cleanup_uploaded_file_missing_is_noop(self):
        from .models import _cleanup_uploaded_file

        with override_settings(MEDIA_ROOT="C:\\nonexistent\\nope"):
            _cleanup_uploaded_file("missing.txt")

    def test_cleanup_uploaded_file_rejects_paths_outside_media(self):
        import pathlib
        import tempfile as _tf

        from .models import _cleanup_uploaded_file

        with _tf.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "media"
            root.mkdir()
            outside = pathlib.Path(d) / "keep.txt"
            outside.write_text("keep", encoding="utf-8")
            with override_settings(MEDIA_ROOT=root):
                _cleanup_uploaded_file("../keep.txt")
            self.assertTrue(outside.exists())

    def test_user_setting_str(self):
        user = User.objects.create_user(username="str-user", password="secret123")
        setting, _ = UserSetting.objects.get_or_create(
            user=user, defaults={"default_summary_ratio": 0.2}
        )
        self.assertIn("str-user", str(setting))

    def test_document_str(self):
        user = User.objects.create_user(username="doc-str-user", password="secret123")
        doc = Document.objects.create(
            user=user, source_type="text", title="My Doc Title", content="x"
        )
        self.assertEqual(str(doc), "My Doc Title")

    def test_document_delete_cleans_uploaded_file_after_commit(self):
        import pathlib
        import tempfile as _tf

        from django.test import override_settings

        with _tf.TemporaryDirectory() as d:
            target = pathlib.Path(d) / "uploads" / "source.txt"
            target.parent.mkdir()
            target.write_text("source", encoding="utf-8")
            with override_settings(MEDIA_ROOT=d), self.captureOnCommitCallbacks(execute=True):
                user = User.objects.create_user(username="file-owner", password="secret123")
                doc = Document.objects.create(
                    user=user,
                    source_type="file",
                    title="Source",
                    uploaded_file="uploads/source.txt",
                    content="source",
                )
                Document.objects.filter(pk=doc.pk).delete()
            self.assertFalse(target.exists())

    def test_summary_persistence_is_idempotent_for_task_id(self):
        from .persistence import summarize_and_persist

        user = User.objects.create_user(username="retry-user", password="secret123")
        args = (user, "text", "manual", "First sentence. Second sentence.", "textrank", 0.5)
        first, _ = summarize_and_persist(*args, idempotency_key="task-retry-1")
        second, _ = summarize_and_persist(*args, idempotency_key="task-retry-1")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Summary.objects.filter(user=user).count(), 1)

    def test_cleanup_uploaded_file_ignores_oserror(self):
        from .models import _cleanup_uploaded_file

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink", side_effect=OSError("denied")),
        ):
            _cleanup_uploaded_file("locked.txt")
