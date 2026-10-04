"""Kiểm thử: flows."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Document, Summary
from .sharing import generate_share_token


class SummaryFlowTests(TestCase):
    def tearDown(self):
        cache.clear()

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret123")

        self.other = User.objects.create_user(username="other", password="secret123")

        self.admin = User.objects.create_superuser(username="admin", password="secret123")

    def test_login_required_for_create_summary(self):
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "test text",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_create_summary_textrank(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "First sentence here. Second sentence follows. Third one is final.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(Summary.objects.count(), 1)

    def test_create_summary_empty_text_returns_error(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.json())

    def test_rate_limit_blocks_rapid_requests(self):
        self.client.login(username="tester", password="secret123")
        self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "A sentence. B sentence. C sentence.",
                "ratio": 0.2,
            },
        )
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "D sentence. E sentence. F sentence.",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 429)

    def test_admin_can_view_all_history(self):
        doc = Document.objects.create(
            user=self.other,
            source_type="text",
            title="Doc",
            content="Content",
        )
        Summary.objects.create(
            document=doc,
            user=self.other,
            title="Other summary",
            method="textrank",
            language="en",
            ratio=0.2,
            summary_text="Text",
        )
        self.client.login(username="admin", password="secret123")
        response = self.client.get(reverse("history"))
        self.assertContains(response, "Other summary")

    def test_user_cannot_view_others_detail(self):
        doc = Document.objects.create(
            user=self.other,
            source_type="text",
            title="Doc",
            content="Content",
        )
        summary = Summary.objects.create(
            document=doc,
            user=self.other,
            title="Private",
            method="textrank",
            language="en",
            ratio=0.2,
            summary_text="Text",
        )
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("history_detail", kwargs={"pk": summary.pk}))
        self.assertEqual(response.status_code, 404)


@override_settings(RATE_LIMIT_SECONDS=0)
class ContentEdgeCaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="edge-test", password="secret123")

        self.client.login(username="edge-test", password="secret123")

    def tearDown(self):
        cache.clear()

    def test_single_character_text(self):
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "A",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_whitespace_only_text_rejected(self):
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "   \n\t  ",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_very_long_text_summarized(self):
        long_text = (
            "Đây là một câu dùng để kiểm tra khả năng xử lý văn bản dài. "
            "Khi dữ liệu lớn, hệ thống vẫn phải tóm tắt chính xác và đầy đủ. "
        ) * 60
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": long_text,
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["summary"])


# ── ROOT_URLCONF nhỏ dùng riêng cho ErrorPageTests ──


class HistoryPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="paginator", password="secret123")

        doc = Document.objects.create(
            user=self.user,
            source_type="text",
            title="Doc",
            content="Content",
        )
        for i in range(15):
            Summary.objects.create(
                document=doc,
                user=self.user,
                title=f"Summary {i}",
                method="textrank",
                language="en",
                ratio=0.2,
                summary_text=f"Text {i}",
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


class PermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="normaluser", password="secret123")

        self.admin = User.objects.create_superuser(username="super", password="secret123")

        self.doc = Document.objects.create(
            user=self.user,
            source_type="text",
            title="My doc",
            content="My content",
        )
        self.summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="My summary",
            method="textrank",
            language="en",
            ratio=0.2,
            summary_text="My text",
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
        User.objects.create_user(username="otheruser", password="secret123")

        self.client.login(username="otheruser", password="secret123")
        response = self.client.post(reverse("history_delete", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 404)

    def test_admin_can_delete_any(self):
        self.client.login(username="super", password="secret123")
        response = self.client.post(reverse("history_delete", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Summary.objects.filter(pk=self.summary.pk).exists())


class DeleteCascadeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cascade-user", password="secret123")

    def test_delete_document_cascades_summary(self):
        doc = Document.objects.create(
            user=self.user,
            source_type="text",
            title="Doc",
            content="Content",
        )
        summary = Summary.objects.create(
            document=doc,
            user=self.user,
            title="Sum",
            method="textrank",
            language="en",
            ratio=0.2,
            summary_text="Text",
        )
        doc.delete()
        self.assertFalse(Summary.objects.filter(pk=summary.pk).exists())

    def test_delete_user_does_not_delete_summary(self):
        doc = Document.objects.create(
            user=self.user,
            source_type="text",
            title="Doc",
            content="Content",
        )
        Summary.objects.create(
            document=doc,
            user=self.user,
            title="Sum",
            method="textrank",
            language="en",
            ratio=0.2,
            summary_text="Text",
        )
        self.user.delete()
        self.assertEqual(Summary.objects.count(), 0)
        self.assertEqual(Document.objects.count(), 0)


class ExportTemplateTests(SimpleTestCase):
    def test_pdf_export_template_compiles(self):
        get_template("summaries/export_pdf.html")


class ExportPdfTests(TestCase):
    """Chỉ chạy được ở nơi weasyprint render thật được (CI Linux có Pango)."""

    def setUp(self):
        self.user = User.objects.create_user(username="pdf-user", password="secret123")
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc PDF", content="Nội dung gốc."
        )
        self.summary = Summary.objects.create(
            document=doc,
            user=self.user,
            title="Bản tóm tắt PDF",
            method="textrank",
            language="vi",
            ratio=0.3,
            summary_text="Câu một. Câu hai.",
        )

    def test_export_pdf_returns_pdf_bytes(self):
        self.client.login(username="pdf-user", password="secret123")
        try:
            response = self.client.get(
                reverse("history_export", kwargs={"pk": self.summary.pk, "format": "pdf"})
            )
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"weasyprint không render được ở môi trường này: {exc}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("attachment;", response["Content-Disposition"])


class ExportMissingDependencyTests(TestCase):
    """Khi thiếu thư viện xuất, endpoint phải trả 500 kèm thông báo rõ, không crash."""

    def setUp(self):
        self.user = User.objects.create_user(username="dep-user", password="secret123")
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content"
        )
        self.summary = Summary.objects.create(
            document=doc,
            user=self.user,
            title="Sum",
            method="textrank",
            language="vi",
            ratio=0.2,
            summary_text="Text",
        )

    def test_missing_weasyprint_returns_helpful_500(self):
        self.client.login(username="dep-user", password="secret123")
        with patch("summaries.exports._check_weasyprint", return_value=False):
            response = self.client.get(
                reverse("history_export", kwargs={"pk": self.summary.pk, "format": "pdf"})
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("weasyprint", response.content.decode())

    def test_missing_docx_returns_helpful_500(self):
        self.client.login(username="dep-user", password="secret123")
        with patch("summaries.exports.HAS_DOCX", False):
            response = self.client.get(
                reverse("history_export", kwargs={"pk": self.summary.pk, "format": "docx"})
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("python-docx", response.content.decode())


class ExportSummaryTests(TestCase):
    """`history_export` — xuất bản tóm tắt ra Markdown/DOCX/PDF."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret123")
        self.other = User.objects.create_user(username="other", password="secret123")
        self.doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc gốc", content="Nội dung gốc."
        )
        self.summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Bản tóm tắt",
            method="textrank",
            language="vi",
            ratio=0.25,
            summary_text="Câu tóm tắt một. Câu tóm tắt hai.",
        )

    def test_export_requires_login(self):
        response = self.client.get(
            reverse("history_export", kwargs={"pk": self.summary.pk, "format": "md"})
        )
        self.assertEqual(response.status_code, 302)

    def test_export_markdown_contains_summary(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(
            reverse("history_export", kwargs={"pk": self.summary.pk, "format": "md"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        body = response.content.decode()
        self.assertIn("# Bản tóm tắt", body)
        self.assertIn("Câu tóm tắt một.", body)
        self.assertIn("25%", body)

    def test_export_docx_returns_ooxml_payload(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(
            reverse("history_export", kwargs={"pk": self.summary.pk, "format": "docx"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            response["Content-Type"],
        )
        self.assertTrue(response.content.startswith(b"PK"), "DOCX phải là file zip")

    def test_export_rejects_unknown_format(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(
            reverse("history_export", kwargs={"pk": self.summary.pk, "format": "txt"})
        )
        self.assertEqual(response.status_code, 400)

    def test_export_hides_other_users_summary(self):
        self.client.login(username="other", password="secret123")
        response = self.client.get(
            reverse("history_export", kwargs={"pk": self.summary.pk, "format": "md"})
        )
        self.assertEqual(response.status_code, 404)

    def test_export_unknown_pk_returns_404(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("history_export", kwargs={"pk": 99999, "format": "md"}))
        self.assertEqual(response.status_code, 404)


class ShareLinkTests(TestCase):
    """`history_share` và `shared_summary` — liên kết chia sẻ có thời hạn."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret123")
        self.other = User.objects.create_user(username="other", password="secret123")
        self.doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content"
        )
        self.summary = Summary.objects.create(
            document=self.doc,
            user=self.user,
            title="Số 1",
            method="textrank",
            language="vi",
            ratio=0.2,
            summary_text="Nội dung tóm tắt",
        )

    def test_create_share_link_requires_login(self):
        response = self.client.post(reverse("history_share", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 302)

    def test_create_share_link_requires_post(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("history_share", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 405)

    def test_create_share_link_returns_absolute_url(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(reverse("history_share", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["expires_in_days"], 7)
        self.assertTrue(payload["share_url"].startswith("http"))
        self.assertIn(payload["token"], payload["share_url"])

    def test_create_share_link_rejects_out_of_range_expiry(self):
        self.client.login(username="tester", password="secret123")
        for value in ("0", "31", "abc"):
            with self.subTest(expiry=value):
                response = self.client.post(
                    reverse("history_share", kwargs={"pk": self.summary.pk}),
                    {"expiry_days": value},
                )
                self.assertEqual(response.status_code, 400)

    def test_create_share_link_hides_other_users_summary(self):
        self.client.login(username="other", password="secret123")
        response = self.client.post(reverse("history_share", kwargs={"pk": self.summary.pk}))
        self.assertEqual(response.status_code, 404)

    def test_shared_page_is_public(self):
        self.client.login(username="tester", password="secret123")
        token = self.client.post(reverse("history_share", kwargs={"pk": self.summary.pk})).json()[
            "token"
        ]
        self.client.logout()

        response = self.client.get(reverse("shared_summary", kwargs={"token": token}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nội dung tóm tắt", response.content.decode())

    def test_shared_page_rejects_tampered_token(self):
        payload, _, signature = generate_share_token(self.summary).partition(".")
        tampered = f"{payload}x.{signature}"

        response = self.client.get(reverse("shared_summary", kwargs={"token": tampered}))
        self.assertEqual(response.status_code, 404)

    def test_shared_page_rejects_expired_token(self):
        token = generate_share_token(self.summary, expiry_days=-1)
        response = self.client.get(reverse("shared_summary", kwargs={"token": token}))
        self.assertEqual(response.status_code, 404)

    def test_shared_page_rejects_garbage_token(self):
        response = self.client.get(reverse("shared_summary", kwargs={"token": "not-a-token"}))
        self.assertEqual(response.status_code, 404)


class TaskStatusTests(TestCase):
    """`check_task_status` — tra trạng thái tác vụ nền."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="secret123")
        self.other = User.objects.create_user(username="other", password="secret123")

    def tearDown(self):
        cache.clear()

    def test_status_requires_login(self):
        response = self.client.get(reverse("check_task_status", kwargs={"task_id": "abc"}))
        self.assertEqual(response.status_code, 302)

    def test_unknown_task_returns_404(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("check_task_status", kwargs={"task_id": "abc"}))
        self.assertEqual(response.status_code, 404)

    def test_task_owned_by_other_user_returns_404(self):
        cache.set("task_owner:abc", self.other.id)
        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("check_task_status", kwargs={"task_id": "abc"}))
        self.assertEqual(response.status_code, 404)

    def test_pending_task_reports_pending(self):
        cache.set("task_owner:abc", self.user.id)
        self.client.login(username="tester", password="secret123")
        with patch("summaries.views.AsyncResult") as async_result:
            async_result.return_value.ready.return_value = False
            response = self.client.get(reverse("check_task_status", kwargs={"task_id": "abc"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "pending"})

    def test_ready_task_returns_result_payload(self):
        cache.set("task_owner:abc", self.user.id)
        self.client.login(username="tester", password="secret123")
        with patch("summaries.views.AsyncResult") as async_result:
            async_result.return_value.ready.return_value = True
            async_result.return_value.result = {"summary": "x"}
            response = self.client.get(reverse("check_task_status", kwargs={"task_id": "abc"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "done")
        self.assertEqual(response.json()["data"]["summary"], "x")
