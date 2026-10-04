"""Kiểm thử: gemini."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserSetting
from .signing import encrypt_value


@override_settings(RATE_LIMIT_SECONDS=0)
class GeminiSummarizeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gemini-test", password="secret123")
        UserSetting.objects.filter(user=self.user).update(gemini_api_key=encrypt_value("fake-key"))
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

    @patch("summaries.readers._get_http_session")
    def test_gemini_summarize_success(self, mock_get_session):
        self._mock_session(mock_get_session)
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "gemini",
                "text": "This is the first sentence. Here is another one. Yet a third sentence.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

    @override_settings(GEMINI_API_KEY="")
    @patch("summaries.readers._get_http_session")
    def test_gemini_summarize_api_key_missing(self, mock_get_session):
        self._mock_session(mock_get_session)
        UserSetting.objects.filter(user=self.user).update(gemini_api_key="")
        cache.clear()
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "gemini",
                "text": "Some text for summary.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])

    @patch("summaries.readers._get_http_session")
    def test_gemini_summarize_empty_response(self, mock_get_session):
        bad_resp = {"candidates": [{"content": {"parts": [{"text": ""}]}}]}
        self._mock_session(mock_get_session, response_data=bad_resp)
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "gemini",
                "text": "First word. Second word. Third word.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 400)

    @patch("summaries.readers._get_http_session")
    def test_gemini_summarize_http_error(self, mock_get_session):
        self._mock_session(mock_get_session, status_code=500)
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "gemini",
                "text": "First word. Second word. Third word.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 400)

    @patch("summaries.readers._get_http_session")
    def test_gemini_summarize_malformed_json(self, mock_get_session):
        bad_resp = {"unexpected": "format"}
        self._mock_session(mock_get_session, response_data=bad_resp)
        response = self.client.post(
            reverse("create_summary"),
            {
                "source_type": "text",
                "method": "gemini",
                "text": "Some text here. More text there.",
                "ratio": 0.3,
            },
        )
        self.assertEqual(response.status_code, 400)


class GeminiErrorBranchTests(TestCase):
    """Unit tests for gemini_summarize error/retry branches (coverage gap).

    Covers 403, 400 (with detail), 429/502/503 retry, retry exhaustion,
    timeout, connection error, Vietnamese prompt, and ratio-to-vietnamese
    length variants.
    """

    def setUp(self):
        import json as _json

        self._json = _json
        self.mock_response = {
            "candidates": [{"content": {"parts": [{"text": "Tóm tắt ngắn gọn."}]}}]
        }

    def _session(self, mock_get_session, responses):
        """responses: list of (status, payload_callable). Side-effect cycles."""
        sess = mock_get_session.return_value

        def _resp_for(status, callback):
            r = MagicMock()
            r.status_code = status
            r.text = "body"
            r.json.side_effect = callback
            if status >= 400:
                from requests.exceptions import HTTPError

                r.raise_for_status.side_effect = HTTPError(f"HTTP {status}")
            return r

        mock_resps = [_resp_for(s, cb) for s, cb in responses]
        sess.post.side_effect = mock_resps
        return sess

    def _call(self):
        from .nlp import gemini_summarize

        return gemini_summarize(
            "Example text for Gemini. This is the first sentence of the input.",
            ratio=0.3,
            language="english",
            user_api_key="fake-key",
        )

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_gemini_403_rejected(self, mock_get_session, _sleep):
        def cb():
            return {"error": {"message": "invalid key"}}

        self._session(mock_get_session, [(403, cb)])
        with self.assertRaises(ValueError):
            self._call()

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_gemini_400_with_detail(self, mock_get_session, _sleep):
        def cb():
            return {"error": {"message": "quota exceeded"}}

        self._session(mock_get_session, [(400, cb)])
        with self.assertRaises(ValueError) as ctx:
            self._call()
        self.assertIn("quota exceeded", str(ctx.exception))

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_gemini_429_retries_then_succeeds(self, mock_get_session, _sleep):
        self._session(
            mock_get_session,
            [
                (429, MagicMock(return_value={})),
                (429, MagicMock(return_value={})),
                (200, MagicMock(return_value=self.mock_response)),
            ],
        )
        result = self._call()
        self.assertIn("summary", result)

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_gemini_502_exhausts_retries(self, mock_get_session, _sleep):
        self._session(
            mock_get_session,
            [
                (502, MagicMock(return_value={})),
                (502, MagicMock(return_value={})),
                (502, MagicMock(return_value={})),
            ],
        )
        with self.assertRaises(ValueError):
            self._call()

    @patch("summaries.readers._get_http_session")
    def test_gemini_timeout(self, mock_get_session):
        from requests.exceptions import Timeout as RequestsTimeout

        sess = mock_get_session.return_value
        sess.post.side_effect = RequestsTimeout("timed out")
        with self.assertRaises(ValueError) as ctx:
            self._call()
        self.assertIn("60", str(ctx.exception))

    @patch("summaries.readers._get_http_session")
    def test_gemini_connection_error(self, mock_get_session):
        from requests.exceptions import ConnectionError as RequestsConnError

        sess = mock_get_session.return_value
        sess.post.side_effect = RequestsConnError("refused")
        with self.assertRaises(ValueError) as ctx:
            self._call()
        self.assertIn("kết nối", str(ctx.exception))

    def test_gemini_requests_import_missing(self):
        from .nlp import gemini_summarize

        with patch.dict("sys.modules", {"requests": None}):
            with self.assertRaises(ValueError) as ctx:
                gemini_summarize("Some text here", user_api_key="k")
        self.assertIn("requests", str(ctx.exception))

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_gemini_400_json_decode_fallback(self, mock_get_session, _sleep):
        def bad_json():
            import json as _json

            raise _json.JSONDecodeError("boom", "doc", 0)

        self._session(mock_get_session, [(400, bad_json)])
        with self.assertRaises(ValueError):
            self._call()


class GeminiPromptBranchTests(TestCase):
    """Cover _build_prompt Vietnamese branch + remaining ratio variants."""

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_vietnamese_prompt_success(self, mock_get_session, _sleep):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Tóm tắt tiếng Việt."}]}}]
        }
        mock_get_session.return_value.post.return_value = resp

        from .nlp import gemini_summarize

        result = gemini_summarize(
            "Đây là câu đầu tiên của văn bản cần tóm tắt bằng tiếng Việt.",
            ratio=0.1,
            language="vietnamese",
            user_api_key="fake-key",
        )
        self.assertIn("summary", result)

    @patch("summaries.nlp.time_module.sleep")
    @patch("summaries.readers._get_http_session")
    def test_vietnamese_ratio_variants(self, mock_get_session, _sleep):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Tóm tắt."}]}}]}
        mock_get_session.return_value.post.return_value = resp

        from .nlp import _ratio_to_vietnamese

        # All ratio branches must produce non-empty strings
        for r in (0.1, 0.2, 0.4, 0.7):
            self.assertTrue(_ratio_to_vietnamese(r))
