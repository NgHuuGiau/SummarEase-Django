"""Kiểm thử: batch."""

import io
import json
import zipfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

TEXT_A = (
    "Django is a high-level Python web framework. "
    "It encourages rapid development and clean, pragmatic design. "
    "The framework follows the batteries-included philosophy."
)
TEXT_B = (
    "TextRank is a graph-based ranking algorithm for text summarization. "
    "It builds a graph of sentences and ranks them by importance. "
    "The method needs no training data and runs quickly."
)


def make_zip(entries: dict) -> SimpleUploadedFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in entries.items():
            zf.writestr(name, body)
    return SimpleUploadedFile("batch.zip", buf.getvalue(), content_type="application/zip")


@override_settings(RATE_LIMIT_SECONDS=0)
class BatchZipTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="batch-user", password="secret123")
        self.url = reverse("batch_summarize_zip")

    def _post(self, archive, **extra):
        return self.client.post(
            self.url,
            {"zip_file": archive, "method": "textrank", "source_type": "file", "ratio": "0.3"},
            **extra,
        )

    def test_requires_login(self):
        self.assertEqual(self._post(make_zip({"a.txt": TEXT_A})).status_code, 302)

    def test_requires_post(self):
        self.client.login(username="batch-user", password="secret123")
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_rejects_missing_zip_file(self):
        self.client.login(username="batch-user", password="secret123")
        response = self.client.post(self.url, {"method": "textrank", "source_type": "file"})
        self.assertEqual(response.status_code, 400)

    def test_summarizes_multiple_text_files(self):
        self.client.login(username="batch-user", password="secret123")
        response = self._post(make_zip({"a.txt": TEXT_A, "b.txt": TEXT_B}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["processed"], 2)
        self.assertEqual(payload["total"], 2)
        self.assertEqual({r["file_name"] for r in payload["results"]}, {"a.txt", "b.txt"})
        for result in payload["results"]:
            self.assertTrue(result["summary"])
            self.assertEqual(result["method"], "textrank")

    def test_rejects_corrupted_archive(self):
        self.client.login(username="batch-user", password="secret123")
        archive = SimpleUploadedFile("bad.zip", b"not a zip file at all", "application/zip")
        response = self._post(archive)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_rejects_archive_without_supported_files(self):
        self.client.login(username="batch-user", password="secret123")
        response = self._post(make_zip({"a.exe": "binary", "b.zip": "nested"}))
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["errors"])

    def test_rejects_empty_archive(self):
        self.client.login(username="batch-user", password="secret123")
        response = self._post(make_zip({}))
        self.assertEqual(response.status_code, 400)

    def test_rejects_path_traversal_entry(self):
        self.client.login(username="batch-user", password="secret123")
        response = self._post(make_zip({"../escape.txt": TEXT_A, "ok.txt": TEXT_B}))
        payload = response.json()
        self.assertEqual(payload["processed"], 1)
        self.assertTrue(any("đường dẫn" in e for e in payload["errors"]))

    def test_rejects_too_many_files(self):
        self.client.login(username="batch-user", password="secret123")
        archive = make_zip({f"f{i}.txt": TEXT_A for i in range(21)})
        response = self._post(archive)
        self.assertEqual(response.status_code, 400)
        self.assertIn("tối đa", response.json()["message"])

    def test_item_failure_does_not_abort_batch(self):
        self.client.login(username="batch-user", password="secret123")
        self.assertEqual(self._post(make_zip({"good.txt": TEXT_B})).json()["processed"], 1)
        with patch("summaries.batch.summarize_and_persist", side_effect=RuntimeError("boom")):
            response = self._post(make_zip({"good.txt": TEXT_B, "bad.txt": TEXT_A}))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["processed"], 0)
        self.assertEqual(len(payload["errors"]), 2)
        for error in payload["errors"]:
            self.assertNotIn("boom", error)


@override_settings(RATE_LIMIT_SECONDS=0)
class BatchUrlsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="batch-url", password="secret123")
        self.url = reverse("batch_summarize_urls")

    def _post(self, body):
        return self.client.post(
            self.url,
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_requires_login(self):
        self.assertEqual(self._post({"urls": ["https://example.com"]}).status_code, 302)

    def test_rejects_invalid_json(self):
        self.client.login(username="batch-url", password="secret123")
        response = self.client.post(self.url, data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_object_json(self):
        self.client.login(username="batch-url", password="secret123")
        for body in ([], None, "text"):
            with self.subTest(body=body):
                self.assertEqual(self._post(body).status_code, 400)

    def test_rejects_empty_url_list(self):
        self.client.login(username="batch-url", password="secret123")
        for body in ({"urls": []}, {}, {"urls": "not-a-list"}, {"urls": [1, 2]}):
            with self.subTest(body=body):
                self.assertEqual(self._post(body).status_code, 400)

    def test_rejects_out_of_range_ratio(self):
        self.client.login(username="batch-url", password="secret123")
        for ratio in (-0.1, 1.5):
            with self.subTest(ratio=ratio):
                response = self._post({"urls": ["https://example.com"], "ratio": ratio})
                self.assertEqual(response.status_code, 400)

    def test_rejects_unknown_method(self):
        self.client.login(username="batch-url", password="secret123")
        response = self._post({"urls": ["https://example.com"], "method": "gpt"})
        self.assertEqual(response.status_code, 400)

    def test_summarizes_each_url(self):
        self.client.login(username="batch-url", password="secret123")
        with patch("summaries.batch.extract_text", return_value=TEXT_A):
            response = self._post({"urls": ["https://example.com/a", "https://example.com/b"]})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["processed"], 2)
        self.assertEqual(
            {r["source_url"] for r in payload["results"]},
            {"https://example.com/a", "https://example.com/b"},
        )

    def test_skips_blank_urls_and_empty_extractions(self):
        self.client.login(username="batch-url", password="secret123")
        with patch("summaries.batch.extract_text", return_value="   "):
            response = self._post({"urls": ["https://example.com/a"]})
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["processed"], 0)
        self.assertTrue(payload["errors"])

    def test_url_failure_does_not_expose_internals(self):
        self.client.login(username="batch-url", password="secret123")
        with patch(
            "summaries.batch.extract_text",
            side_effect=RuntimeError("secret server detail"),
        ):
            response = self._post({"urls": ["https://example.com/a"]})
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["processed"], 0)
        self.assertNotIn("secret server detail", str(payload))

    def test_rejects_too_many_urls(self):
        self.client.login(username="batch-url", password="secret123")
        response = self._post({"urls": [f"https://example.com/{i}" for i in range(21)]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("tối đa", response.json()["message"])
