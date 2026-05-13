from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Document, Summary, UserProfile, UserSetting


class SummaryFlowTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="tester", password="secret123")
        UserProfile.objects.create(user=self.user, role="user")
        UserSetting.objects.create(user=self.user, default_summary_ratio=0.2, language_preference="auto")
        self.other_user = User.objects.create_user(username="member2", password="secret123")
        UserProfile.objects.create(user=self.other_user, role="user")
        UserSetting.objects.create(user=self.other_user, default_summary_ratio=0.3, language_preference="auto")
        self.admin = User.objects.create_user(username="admin", password="secret123", is_staff=True, is_superuser=True)
        UserProfile.objects.create(user=self.admin, role="admin")
        UserSetting.objects.create(user=self.admin, default_summary_ratio=0.2, language_preference="auto")

    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_login_required_for_create_summary(self):
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "Day la mot van ban ngan de kiem thu luong tom tat co ban.",
                "ratio": 0.2,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_create_summary_as_authenticated_user(self):
        self.client.login(username="tester", password="secret123")
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "textrank",
                "text": "Day la mot van ban ngan de kiem thu luong tom tat co ban. Van ban nay co nhieu cau hon de bo tom tat hoat dong on dinh.",
                "ratio": 0.5,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Summary.objects.count(), 1)

    def test_create_summary_returns_serialized_errors(self):
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
        self.assertEqual(response.json()["errors"]["text"], ["Nhập văn bản cần tóm tắt."])

    def test_admin_can_view_all_history_entries(self):
        document = Document.objects.create(
            user=self.other_user,
            source_type="text",
            title="Tai lieu test",
            source_name="Van ban",
            content="Noi dung goc",
        )
        Summary.objects.create(
            document=document,
            user=self.other_user,
            title="Ban tom tat cua user khac",
            method="textrank",
            language="vi",
            ratio=0.2,
            summary_text="Noi dung tom tat",
        )

        self.client.login(username="admin", password="secret123")
        response = self.client.get(reverse("history"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ban tom tat cua user khac")
        self.assertContains(response, "member2")

    def test_regular_user_cannot_view_other_users_history_detail(self):
        document = Document.objects.create(
            user=self.other_user,
            source_type="text",
            title="Tai lieu rieng",
            source_name="Van ban",
            content="Noi dung goc",
        )
        summary = Summary.objects.create(
            document=document,
            user=self.other_user,
            title="Ban ghi rieng",
            method="textrank",
            language="vi",
            ratio=0.2,
            summary_text="Noi dung tom tat",
        )

        self.client.login(username="tester", password="secret123")
        response = self.client.get(reverse("history_detail", kwargs={"pk": summary.pk}))

        self.assertEqual(response.status_code, 404)
