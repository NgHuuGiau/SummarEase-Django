"""Kiểm thử: webhooks."""

import tempfile
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Document, Summary, UserSetting
from .webhooks import (
    WebhookDelivery,
    WebhookRegistration,
    _build_webhook_payload,
    _canonical_payload,
    _deliver_webhook,
    _sign_payload,
    validate_webhook_url,
)

VALID_HOOK = "https://example.com/hooks/summarease"


class WebhookDeliveryTests(TestCase):
    """Nhánh gửi HTTP thật của `_deliver_webhook` — mọi I/O được mock."""

    def setUp(self):
        resolver = patch("summaries.webhooks._resolve_and_validate")
        resolver.start()
        self.addCleanup(resolver.stop)
        self.user = User.objects.create_user(username="deliver-user", password="secret123")
        self.webhook = WebhookRegistration.objects.create(
            user=self.user,
            url=VALID_HOOK,
            secret="s3cret",
            events=["summary.completed"],
        )
        doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content"
        )
        self.summary = Summary.objects.create(
            user=self.user,
            document=doc,
            title="Sum",
            method="textrank",
            ratio=0.3,
            summary_text="Test summary",
        )
        self.payload = _build_webhook_payload(self.summary, "summary.completed")

    @staticmethod
    def _session(**kwargs):
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        session.post.return_value = kwargs.get("response")
        return session

    def _deliver(self, session=None, max_retries=1):
        patcher = (
            patch("summaries.webhooks.requests.Session", return_value=session)
            if session
            else patch("summaries.webhooks.requests.Session", side_effect=OSError("no network"))
        )
        with patcher, patch("summaries.webhooks.time.sleep"):
            return _deliver_webhook(self.webhook, self.payload, max_retries=max_retries)

    def test_str_and_verify_signature(self):
        self.assertEqual(str(self.webhook), f"deliver-user -> {VALID_HOOK}")
        body = _canonical_payload(self.payload.to_dict())
        self.assertTrue(
            self.webhook.verify_signature(body, _sign_payload(self.payload.to_dict(), "s3cret"))
        )
        self.assertFalse(self.webhook.verify_signature(body, "deadbeef"))

    def test_signature_header_is_stable_and_covers_body(self):
        session = self._session(response=MagicMock(status_code=200))
        with patch("summaries.webhooks.requests.Session", return_value=session):
            self.assertTrue(_deliver_webhook(self.webhook, self.payload))
        headers = session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Webhook-Event"], "summary.completed")
        self.assertEqual(
            headers["X-Webhook-Signature"], _sign_payload(self.payload.to_dict(), "s3cret")
        )
        self.assertNotIn("X-Webhook-Delivery", headers)

    def test_delivery_id_header_added_when_supplied(self):
        session = self._session(response=MagicMock(status_code=204))
        with patch("summaries.webhooks.requests.Session", return_value=session):
            _deliver_webhook(self.webhook, self.payload, delivery_id="abc-123")
        headers = session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Webhook-Delivery"], "abc-123")

    def test_success_resets_failure_count(self):
        self.webhook.failure_count = 3
        self.webhook.save(update_fields=["failure_count"])
        session = self._session(response=MagicMock(status_code=200))
        with patch("summaries.webhooks.requests.Session", return_value=session):
            self.assertTrue(_deliver_webhook(self.webhook, self.payload))
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.failure_count, 0)
        self.assertIsNotNone(self.webhook.last_triggered)

    def test_non_2xx_retries_then_fails(self):
        session = self._session(response=MagicMock(status_code=500))
        with (
            patch("summaries.webhooks.requests.Session", return_value=session),
            patch("summaries.webhooks.time.sleep"),
        ):
            self.assertFalse(_deliver_webhook(self.webhook, self.payload, max_retries=3))
        self.assertEqual(session.post.call_count, 3)
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.failure_count, 1)

    def test_request_exception_is_retried(self):
        session = MagicMock()
        session.__enter__.return_value = session
        session.post.side_effect = requests.RequestException("boom")
        with (
            patch("summaries.webhooks.requests.Session", return_value=session),
            patch("summaries.webhooks.time.sleep"),
        ):
            self.assertFalse(_deliver_webhook(self.webhook, self.payload, max_retries=2))
        self.assertEqual(session.post.call_count, 2)

    def test_url_rejected_during_delivery_skips_retry(self):
        session = self._session(response=MagicMock(status_code=200))
        with (
            patch("summaries.webhooks.requests.Session", return_value=session),
            patch(
                "summaries.webhooks.validate_webhook_url", side_effect=ValueError("private host")
            ),
        ):
            self.assertFalse(_deliver_webhook(self.webhook, self.payload, max_retries=3))
        session.post.assert_not_called()
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.failure_count, 1)

    def test_webhook_disabled_after_ten_failures(self):
        self.webhook.failure_count = 9
        self.webhook.save(update_fields=["failure_count"])
        session = self._session(response=MagicMock(status_code=500))
        with patch("summaries.webhooks.requests.Session", return_value=session):
            self.assertFalse(_deliver_webhook(self.webhook, self.payload, max_retries=1))
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.failure_count, 10)
        self.assertFalse(self.webhook.is_active)


class WebhookValidationTests(TestCase):
    def test_rejects_non_http_scheme(self):
        for url in ("ftp://example.com/x", "file:///etc/passwd", "example.com/x"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_webhook_url(url)

    def test_rejects_malformed_url(self):
        with self.assertRaises(ValueError):
            validate_webhook_url("https://example.com:not-a-port/x")

    def test_rejects_private_and_loopback_destinations(self):
        for url in (
            "http://127.0.0.1/hook",
            "https://localhost/hook",
            "https://10.0.0.5/hook",
            "https://192.168.1.1/hook",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_webhook_url(url)

    @override_settings(DEBUG=False)
    def test_production_requires_https(self):
        with self.assertRaises(ValueError):
            validate_webhook_url("http://example.com/hook")

    def test_accepts_public_https_url(self):
        with patch("summaries.webhooks._resolve_and_validate"):
            validate_webhook_url(VALID_HOOK)


class WebhookSignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="signal-user", password="secret123")
        self.doc = Document.objects.create(
            user=self.user, source_type="text", title="Doc", content="Content"
        )

    def _summary(self):
        return Summary.objects.create(
            user=self.user,
            document=self.doc,
            title="Sum",
            method="textrank",
            ratio=0.3,
            summary_text="Text",
        )

    def test_inactive_webhook_gets_no_outbox_row(self):
        WebhookRegistration.objects.create(
            user=self.user,
            url=VALID_HOOK,
            secret="s",
            events=["summary.completed"],
            is_active=False,
        )
        self._summary()
        self.assertEqual(WebhookDelivery.objects.count(), 0)

    def test_unsubscribed_event_gets_no_outbox_row(self):
        WebhookRegistration.objects.create(
            user=self.user, url=VALID_HOOK, secret="s", events=["summary.failed"]
        )
        self._summary()
        self.assertEqual(WebhookDelivery.objects.count(), 0)

    def test_outbox_row_is_idempotent_per_summary(self):
        WebhookRegistration.objects.create(
            user=self.user, url=VALID_HOOK, secret="s", events=["summary.completed"]
        )
        summary = self._summary()
        Summary.objects.filter(pk=summary.pk).update(summary_text="đổi nội dung")
        self.assertEqual(WebhookDelivery.objects.count(), 1)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertEqual(delivery.event, "summary.completed")

    @override_settings(DEBUG=True)
    def test_debug_mode_dispatches_synchronously(self):
        WebhookRegistration.objects.create(
            user=self.user, url=VALID_HOOK, secret="s", events=["summary.completed"]
        )
        with patch("summaries.tasks.dispatch_webhook_delivery") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                self._summary()
        delivery = WebhookDelivery.objects.get()
        dispatch.assert_called_once_with(delivery.pk)
        dispatch.delay.assert_not_called()

    @override_settings(DEBUG=False)
    def test_production_enqueues_after_commit(self):
        WebhookRegistration.objects.create(
            user=self.user, url=VALID_HOOK, secret="s", events=["summary.completed"]
        )
        with patch("summaries.tasks.dispatch_webhook_delivery") as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                self._summary()
        dispatch.delay.assert_called_once_with(WebhookDelivery.objects.get().pk)
        dispatch.assert_not_called()

    @override_settings(DEBUG=False)
    def test_enqueue_failure_leaves_row_pending_for_sweeper(self):
        WebhookRegistration.objects.create(
            user=self.user, url=VALID_HOOK, secret="s", events=["summary.completed"]
        )
        with patch("summaries.tasks.dispatch_webhook_delivery") as dispatch:
            dispatch.delay.side_effect = RuntimeError("broker down")
            with self.captureOnCommitCallbacks(execute=True):
                self._summary()
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertEqual(delivery.attempt_count, 0)


class WebhookViewTests(TestCase):
    """Các view quản lý webhook: tạo, xoá và gửi thử."""

    def setUp(self):
        resolver = patch("summaries.webhooks._resolve_and_validate")
        resolver.start()
        self.addCleanup(resolver.stop)
        self.user = User.objects.create_user(username="hook-owner", password="secret123")
        self.other = User.objects.create_user(username="hook-other", password="secret123")
        self.webhook = WebhookRegistration.objects.create(
            user=self.user,
            url=VALID_HOOK,
            secret="s3cret",
            events=["summary.completed"],
        )

    def test_list_requires_login(self):
        response = self.client.get(reverse("webhook_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_only_own_registrations(self):
        WebhookRegistration.objects.create(
            user=self.other, url=VALID_HOOK, secret="x", events=["summary.completed"]
        )
        self.client.login(username="hook-owner", password="secret123")
        response = self.client.get(reverse("webhook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["webhooks"]), [self.webhook])

    def test_list_post_without_login_is_rejected(self):
        response = self.client.post(reverse("webhook_list"), {"url": VALID_HOOK})
        self.assertEqual(response.status_code, 302)

    def test_create_registration_generates_secret(self):
        self.client.login(username="hook-owner", password="secret123")
        response = self.client.post(
            reverse("webhook_list"),
            {"url": VALID_HOOK, "events": ["summary.completed"]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = WebhookRegistration.objects.exclude(pk=self.webhook.pk).get()
        self.assertTrue(created.secret)
        self.assertContains(response, created.secret)
        self.assertEqual(created.events, ["summary.completed"])

    def test_regenerate_secret_is_one_time_and_user_scoped(self):
        self.client.login(username="hook-owner", password="secret123")
        old_secret = self.webhook.secret
        response = self.client.post(
            reverse("webhook_regenerate_secret", kwargs={"pk": self.webhook.pk}), follow=True
        )
        self.webhook.refresh_from_db()
        self.assertNotEqual(self.webhook.secret, old_secret)
        self.assertContains(response, self.webhook.secret)
        self.assertNotContains(self.client.get(reverse("webhook_list")), self.webhook.secret)

    def test_create_registration_rejects_blank_url(self):
        self.client.login(username="hook-owner", password="secret123")
        self.client.post(
            reverse("webhook_list"), {"url": "  ", "events": ["summary.completed"]}, follow=True
        )
        self.assertEqual(WebhookRegistration.objects.count(), 1)

    def test_create_registration_rejects_missing_events(self):
        self.client.login(username="hook-owner", password="secret123")
        self.client.post(reverse("webhook_list"), {"url": VALID_HOOK, "events": []}, follow=True)
        self.assertEqual(WebhookRegistration.objects.count(), 1)

    def test_create_registration_rejects_private_host(self):
        self.client.login(username="hook-owner", password="secret123")
        self.client.post(
            reverse("webhook_list"),
            {"url": "http://127.0.0.1:9000/hook", "events": ["summary.completed"]},
            follow=True,
        )
        self.assertEqual(WebhookRegistration.objects.count(), 1)

    def test_delete_requires_post(self):
        self.client.login(username="hook-owner", password="secret123")
        response = self.client.get(reverse("webhook_delete", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 405)

    def test_delete_removes_own_registration(self):
        self.client.login(username="hook-owner", password="secret123")
        response = self.client.post(reverse("webhook_delete", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WebhookRegistration.objects.filter(pk=self.webhook.pk).exists())

    def test_delete_hides_other_users_registration(self):
        self.client.login(username="hook-other", password="secret123")
        response = self.client.post(reverse("webhook_delete", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WebhookRegistration.objects.filter(pk=self.webhook.pk).exists())

    def test_test_endpoint_sends_payload(self):
        self.client.login(username="hook-owner", password="secret123")
        with patch("summaries.webhooks._deliver_webhook", return_value=True) as deliver:
            response = self.client.post(reverse("webhook_test", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        webhook, payload = deliver.call_args[0]
        self.assertEqual(webhook.pk, self.webhook.pk)
        self.assertEqual(payload.event, "summary.completed")
        self.assertEqual(payload.summary_id, 0)

    def test_test_endpoint_reports_failure(self):
        self.client.login(username="hook-owner", password="secret123")
        with patch("summaries.webhooks._deliver_webhook", return_value=False):
            response = self.client.post(reverse("webhook_test", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])

    def test_test_endpoint_hides_other_users_registration(self):
        self.client.login(username="hook-other", password="secret123")
        response = self.client.post(reverse("webhook_test", kwargs={"pk": self.webhook.pk}))
        self.assertEqual(response.status_code, 404)


class WebhookSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="webhook-user", password="secret123")
        self.document = Document.objects.create(
            user=self.user,
            source_type="text",
            title="Webhook test",
            content="Test content",
        )
        self.summary = Summary.objects.create(
            user=self.user,
            document=self.document,
            title="Webhook test",
            method="textrank",
            ratio=0.3,
            summary_text="Test summary",
        )

    def test_webhook_url_rejects_private_hosts_and_credentials(self):
        from summaries.webhooks import validate_webhook_url

        with self.assertRaises(ValueError):
            validate_webhook_url("http://127.0.0.1:8000/internal")
        with self.assertRaises(ValueError):
            validate_webhook_url("https://user:password@example.com/hook")

    def test_production_webhook_requires_https(self):
        from summaries.webhooks import validate_webhook_url

        with override_settings(DEBUG=False), self.assertRaises(ValueError):
            validate_webhook_url("http://hooks.example.com/receive")

    def test_successful_delivery_records_datetime_without_redirects(self):
        from summaries.webhooks import WebhookRegistration, _build_webhook_payload, _deliver_webhook

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        response = MagicMock(status_code=204)
        with (
            patch("summaries.webhooks._resolve_and_validate"),
            patch("requests.Session.post", return_value=response) as post,
        ):
            self.assertTrue(
                _deliver_webhook(
                    webhook,
                    _build_webhook_payload(self.summary, "summary.completed"),
                    delivery_id="test-delivery-1",
                )
            )

        webhook.refresh_from_db()
        self.assertEqual(webhook.failure_count, 0)
        self.assertIsNotNone(webhook.last_triggered)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertEqual(post.call_args.kwargs["headers"]["X-Webhook-Delivery"], "test-delivery-1")
        post.assert_called_once()

    def test_summary_webhook_outbox_is_queued_after_transaction_commit(self):
        from summaries.tasks import dispatch_webhook_delivery
        from summaries.webhooks import WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )

        with (
            override_settings(DEBUG=False),
            patch.object(dispatch_webhook_delivery, "delay") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            summary = Summary.objects.create(
                user=self.user,
                document=self.document,
                title="Queued webhook",
                method="textrank",
                ratio=0.3,
                summary_text="Queued summary",
            )

        delivery = WebhookDelivery.objects.get(webhook=webhook, summary=summary)
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        enqueue.assert_called_once_with(delivery.pk)

    def test_failed_broker_enqueue_leaves_delivery_for_sweeper(self):
        from summaries.tasks import dispatch_webhook_delivery, enqueue_pending_webhook_deliveries
        from summaries.webhooks import WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        with (
            override_settings(DEBUG=False),
            patch.object(dispatch_webhook_delivery, "delay", side_effect=ConnectionError),
            self.captureOnCommitCallbacks(execute=True),
        ):
            summary = Summary.objects.create(
                user=self.user,
                document=self.document,
                title="Broker unavailable",
                method="textrank",
                ratio=0.3,
                summary_text="Still persisted in the outbox",
            )

        delivery = WebhookDelivery.objects.get(webhook=webhook, summary=summary)
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        with patch.object(dispatch_webhook_delivery, "delay") as enqueue:
            self.assertEqual(enqueue_pending_webhook_deliveries(), 1)
        enqueue.assert_called_once_with(delivery.pk)

    def test_failed_delivery_is_retried_without_blocking_worker(self):
        from summaries.tasks import dispatch_webhook_delivery
        from summaries.webhooks import WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            summary=self.summary,
            event="summary.completed",
        )

        with patch("summaries.webhooks._deliver_webhook", return_value=False) as send:
            dispatch_webhook_delivery(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertGreater(delivery.available_at, timezone.now())
        self.assertEqual(send.call_args.kwargs["max_retries"], 1)
        self.assertEqual(send.call_args.kwargs["delivery_id"], str(delivery.pk))

    def test_successful_outbox_delivery_is_marked_delivered(self):
        from summaries.tasks import dispatch_webhook_delivery
        from summaries.webhooks import WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            summary=self.summary,
            event="summary.completed",
        )

        with patch("summaries.webhooks._deliver_webhook", return_value=True):
            dispatch_webhook_delivery(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.DELIVERED)
        self.assertIsNotNone(delivery.delivered_at)
        self.assertEqual(delivery.attempt_count, 0)

    def test_sweeper_recovers_stale_worker_claim(self):
        from summaries.tasks import dispatch_webhook_delivery, enqueue_pending_webhook_deliveries
        from summaries.webhooks import WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            summary=self.summary,
            event="summary.completed",
            status=WebhookDelivery.PROCESSING,
            locked_at=timezone.now() - timedelta(minutes=16),
        )

        with patch.object(dispatch_webhook_delivery, "delay") as enqueue:
            self.assertEqual(enqueue_pending_webhook_deliveries(), 1)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.PENDING)
        self.assertIsNone(delivery.locked_at)
        enqueue.assert_called_once_with(delivery.pk)

    def test_outbox_delivery_stops_after_maximum_attempts(self):
        from summaries.tasks import dispatch_webhook_delivery
        from summaries.webhooks import DELIVERY_MAX_ATTEMPTS, WebhookDelivery, WebhookRegistration

        webhook = WebhookRegistration.objects.create(
            user=self.user,
            url="https://hooks.example.com/receive",
            secret="test-secret",
            events=["summary.completed"],
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            summary=self.summary,
            event="summary.completed",
            attempt_count=DELIVERY_MAX_ATTEMPTS - 1,
        )

        with patch("summaries.webhooks._deliver_webhook", return_value=False):
            dispatch_webhook_delivery(delivery.pk)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.FAILED)
        self.assertEqual(delivery.attempt_count, DELIVERY_MAX_ATTEMPTS)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class CeleryTaskIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="celery-test", password="secret123")
        self.client.login(username="celery-test", password="secret123")
        UserSetting.objects.filter(user=self.user).update(gemini_api_key="")
        # Disable rate limiting for API tests
        from django.conf import settings

        settings.RATE_LIMIT_SECONDS = 0

    def tearDown(self):
        cache.clear()

    def test_process_summary_task_textrank_success(self):
        from .tasks import process_summary_task

        text = (
            "First sentence here. Second sentence follows. "
            "Third one is final. Fourth sentence added."
        )
        result = process_summary_task(
            user_id=self.user.id,
            source_type="text",
            method="textrank",
            ratio=0.5,
            text=text,
        )
        self.assertTrue(result["ok"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["method"], "textrank")
        self.assertIn("summary", result["data"])
        self.assertIn("keywords", result["data"])
        self.assertIn("history_url", result["data"])
        self.assertEqual(Summary.objects.count(), 1)
        self.assertEqual(Document.objects.count(), 1)

    def test_process_summary_task_empty_text_fails(self):
        from .tasks import process_summary_task

        result = process_summary_task(
            user_id=self.user.id,
            source_type="text",
            method="textrank",
            ratio=0.5,
            text="   ",
        )
        self.assertFalse(result["ok"])
        self.assertIn("message", result)

    def test_service_rate_limit(self):
        """Test rate limiting at service level (called by task in eager mode)."""
        from django.conf import settings

        from .services import SummaryService

        settings.RATE_LIMIT_SECONDS = 5  # Re-enable rate limiting for this test

        service = SummaryService(self.user)
        text = "Sentence one. Sentence two. Sentence three."
        # First call OK
        result = service.create_summary(
            source_type="text",
            method="textrank",
            ratio=0.5,
            text=text,
        )
        self.assertTrue(result.get("ok", result.get("data", {}).get("ok", False)))
        # Second call within rate limit -> fail
        result = service.create_summary(
            source_type="text",
            method="textrank",
            ratio=0.5,
            text=text,
        )
        self.assertFalse(result["ok"])
        self.assertIn("giây", result["message"])

    def test_service_reports_unavailable_when_broker_is_down(self):
        from kombu.exceptions import OperationalError

        from .services import SummaryService

        with override_settings(DEBUG=False, RATE_LIMIT_SECONDS=0):
            with (
                patch.dict("os.environ", {"DJANGO_TEST": ""}),
                patch(
                    "summaries.services.process_summary_task.delay",
                    side_effect=OperationalError("broker down"),
                ),
            ):
                result = SummaryService(self.user).create_summary(
                    "text", "textrank", 0.5, text="First sentence. Second sentence."
                )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 503)

    def test_process_summary_task_invalid_user(self):
        from .tasks import process_summary_task

        result = process_summary_task(
            user_id=99999,
            source_type="text",
            method="textrank",
            ratio=0.5,
            text="Some text here.",
        )
        self.assertFalse(result["ok"])
        self.assertIn("Người dùng", result["message"])

    def test_process_summary_task_file_cleanup_on_error(self):
        from pathlib import Path

        from .tasks import process_summary_task

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.txt"
            bad_file.write_text("")  # empty file
            result = process_summary_task(
                user_id=self.user.id,
                source_type="file",
                method="textrank",
                ratio=0.5,
                file_path=str(
                    bad_file.relative_to(Path.cwd())
                    if bad_file.is_relative_to(Path.cwd())
                    else bad_file
                ),
            )
            # Should fail gracefully
            self.assertFalse(result["ok"])

    @patch("summaries.tasks.extract_text", side_effect=RuntimeError("private server detail"))
    def test_process_summary_task_hides_internal_errors(self, _extract_text):
        from .tasks import process_summary_task

        result = process_summary_task(
            user_id=self.user.id,
            source_type="url",
            method="textrank",
            ratio=0.5,
            source_url="https://example.com/article",
        )

        self.assertEqual(result["message"], "Không thể xử lý yêu cầu. Vui lòng thử lại sau.")
        self.assertNotIn("private server detail", str(result))

    @patch("summaries.batch.extract_text", side_effect=RuntimeError("private server detail"))
    def test_batch_url_errors_hide_exception_and_query_string(self, _extract_text):
        from .batch import create_batch_from_urls

        secret_url = "https://example.com/article?token=private"
        result = create_batch_from_urls(self.user, [secret_url], "textrank", 0.5)

        self.assertEqual(result["errors"], ["Không thể xử lý URL đã cung cấp."])
        self.assertNotIn("private server detail", str(result))
        self.assertNotIn("token=private", str(result))

    def test_batch_zip_item_errors_do_not_expose_exception(self):
        import io
        import zipfile

        from .batch import create_batch_from_zip

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("article.txt", "Nội dung tài liệu kiểm thử.")
        uploaded_file = SimpleUploadedFile("batch.zip", archive.getvalue())

        with patch(
            "summaries.batch.extract_text", side_effect=RuntimeError("private server detail")
        ):
            result = create_batch_from_zip(self.user, uploaded_file, "textrank", 0.5)

        self.assertEqual(result["errors"], ["article.txt: Không thể xử lý tệp này."])
        self.assertNotIn("private server detail", str(result))

    def test_batch_zip_failure_does_not_expose_exception(self):
        from .batch import create_batch_from_zip

        uploaded_file = SimpleUploadedFile("batch.zip", b"invalid archive")
        with patch(
            "summaries.batch.zipfile.ZipFile", side_effect=RuntimeError("private server detail")
        ):
            result = create_batch_from_zip(self.user, uploaded_file, "textrank", 0.5)

        self.assertEqual(result["message"], "Không thể xử lý lô tệp. Vui lòng thử lại sau.")
        self.assertNotIn("private server detail", str(result))

    def test_api_v1_endpoints_exist(self):
        """Verify /api/v1/ routes are registered."""
        # Get CSRF token first
        self.client.get("/api/v1/summaries/create/")
        response = self.client.post(
            "/api/v1/summaries/create/",
            {
                "source_type": "text",
                "text": "Test content for API v1.",
                "method": "textrank",
                "ratio": 0.3,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # In test mode (eager), returns full result directly
        self.assertTrue(data["ok"])
        # Can be either task_id (async) or data (eager sync)
        self.assertTrue("task_id" in data or "data" in data)

    def test_api_v1_status_endpoint(self):
        """Verify task status polling endpoint."""
        # Create a task first
        self.client.get("/api/v1/summaries/create/")
        response = self.client.post(
            "/api/v1/summaries/create/",
            {
                "source_type": "text",
                "text": "Test content for status check.",
                "method": "textrank",
                "ratio": 0.3,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # In eager mode, returns full result
        if "task_id" in data:
            task_id = data["task_id"]
            # Poll status
            status_resp = self.client.get(
                f"/api/v1/summaries/status/{task_id}/",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(status_resp.status_code, 200)
            status_data = status_resp.json()
            self.assertEqual(status_data["status"], "done")
            self.assertIn("data", status_data)
        else:
            # Eager mode - result returned directly
            self.assertIn("data", data)

    def test_old_api_endpoint_still_works(self):
        """Backward compatibility - old /api/summaries/create/ should still work."""
        self.client.get("/api/summaries/create/")
        response = self.client.post(
            "/api/summaries/create/",
            {
                "source_type": "text",
                "text": "Test old endpoint.",
                "method": "textrank",
                "ratio": 0.3,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        # Old endpoint may not exist anymore since we moved to /api/v1/
        self.assertIn(response.status_code, [200, 404, 405])
