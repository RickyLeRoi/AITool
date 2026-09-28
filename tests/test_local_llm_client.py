# tests/test_local_llm_client.py
import importlib
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import local_llm_client


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _ConfiguredTestCase(unittest.TestCase):
    """Base for tests that exercise chat()/status() request-building logic
    and don't care about .env/env-var resolution itself: patches
    DEFAULT_BASE_URL/DEFAULT_MODEL directly to fixed test values, so these
    tests need neither a real .env nor knowledge of what it contains."""

    def setUp(self):
        self._patchers = [
            patch("local_llm_client.DEFAULT_BASE_URL", "http://test.invalid/v1"),
            patch("local_llm_client.DEFAULT_MODEL", "test-model"),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()


class TestLocalLlmClient(_ConfiguredTestCase):
    def test_unreachable_backend_returns_labeled_error_not_exception(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = local_llm_client.chat("hello")
        self.assertIn("[local-llm unavailable]", result)
        self.assertIn("refused", result)

    def test_successful_response_is_extracted_and_labeled(self):
        payload = json.dumps(
            {"choices": [{"message": {"content": "a short summary"}}]}
        ).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = local_llm_client.chat("summarize this")
        self.assertIn("local-model draft, verify", result)
        self.assertIn("a short summary", result)

    def test_unexpected_response_shape_reported_not_raised(self):
        payload = json.dumps({"unexpected": "shape"}).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = local_llm_client.chat("hello")
        self.assertIn("unexpected response shape", result)

    def test_401_response_reports_unauthorized_with_hint(self):
        http_error = urllib.error.HTTPError(
            url="http://example/v1/chat/completions", code=401, msg="Unauthorized", hdrs=None, fp=io.BytesIO()
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = local_llm_client.chat("hello")
        self.assertIn("[local-llm unauthorized]", result)
        self.assertIn("LOCAL_LLM_API_KEY", result)

    def test_403_response_also_reports_unauthorized(self):
        http_error = urllib.error.HTTPError(
            url="http://example/v1/chat/completions", code=403, msg="Forbidden", hdrs=None, fp=io.BytesIO()
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = local_llm_client.chat("hello")
        self.assertIn("[local-llm unauthorized]", result)

    def test_other_http_error_is_not_mislabeled_as_unauthorized(self):
        http_error = urllib.error.HTTPError(
            url="http://example/v1/chat/completions", code=500, msg="Server Error", hdrs=None, fp=io.BytesIO()
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = local_llm_client.chat("hello")
        self.assertIn("[local-llm error]", result)
        self.assertNotIn("unauthorized", result)

    def test_missing_base_url_reports_not_configured_without_any_network_call(self):
        with patch("local_llm_client.DEFAULT_BASE_URL", None):
            with patch("urllib.request.urlopen") as mock_urlopen:
                result = local_llm_client.chat("hello")
        mock_urlopen.assert_not_called()
        self.assertIn("[local-llm not configured]", result)
        self.assertIn("LOCAL_LLM_BASE_URL", result)

    def test_missing_model_reports_not_configured(self):
        with patch("local_llm_client.DEFAULT_MODEL", None):
            result = local_llm_client.chat("hello")
        self.assertIn("[local-llm not configured]", result)
        self.assertIn("LOCAL_LLM_MODEL", result)


class TestLocalLlmClientEnvConfig(unittest.TestCase):
    """LOCAL_LLM_BASE_URL / LOCAL_LLM_MODEL / LOCAL_LLM_API_KEY are read once,
    at module import time - these tests reload the module under a patched
    environment and always reload it back to the real environment afterwards
    so later tests see the module's normal state.

    A real ".env" may exist on disk in this dev environment (it does - see
    CLAUDE.md). Left alone, "importlib.reload" would re-run "load_dotenv()"
    and pull in whatever that real file happens to contain, making these
    tests depend on developer-machine state instead of the values each test
    explicitly sets. Patching "_shared.load_dotenv" to a no-op for the whole
    class removes that dependency - "from _shared import load_dotenv" is
    re-evaluated on every reload, so it picks up the patched version too.
    """

    def setUp(self):
        self._dotenv_patcher = patch("_shared.load_dotenv")
        self._dotenv_patcher.start()

    def tearDown(self):
        self._dotenv_patcher.stop()
        importlib.reload(local_llm_client)

    def test_env_vars_are_read_into_module_constants(self):
        with patch.dict(os.environ, {
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:4141/v1",
            "LOCAL_LLM_MODEL": "custom-model",
            "LOCAL_LLM_API_KEY": "secret123",
        }):
            importlib.reload(local_llm_client)
            self.assertEqual(local_llm_client.DEFAULT_BASE_URL, "http://127.0.0.1:4141/v1")
            self.assertEqual(local_llm_client.DEFAULT_MODEL, "custom-model")
            self.assertEqual(local_llm_client.DEFAULT_API_KEY, "secret123")

    def test_missing_env_vars_leave_constants_unset_no_hardcoded_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(local_llm_client)
            self.assertIsNone(local_llm_client.DEFAULT_BASE_URL)
            self.assertIsNone(local_llm_client.DEFAULT_MODEL)
            self.assertIsNone(local_llm_client.DEFAULT_API_KEY)
            self.assertIn("[local-llm not configured]", local_llm_client.chat("hi"))

    def test_request_is_sent_to_the_configured_base_url_and_model(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            captured["body"] = json.loads(req.data.decode("utf-8"))
            payload = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
            return _FakeResponse(payload)

        with patch.dict(os.environ, {
            "LOCAL_LLM_BASE_URL": "http://127.0.0.1:4141/v1",
            "LOCAL_LLM_MODEL": "custom-model",
        }):
            importlib.reload(local_llm_client)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                local_llm_client.chat("hi")

        self.assertEqual(captured["req"].full_url, "http://127.0.0.1:4141/v1/chat/completions")
        self.assertEqual(captured["body"]["model"], "custom-model")

    def test_authorization_header_sent_when_api_key_configured(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            payload = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
            return _FakeResponse(payload)

        with patch.dict(os.environ, {
            "LOCAL_LLM_BASE_URL": "http://test.invalid/v1",
            "LOCAL_LLM_MODEL": "test-model",
            "LOCAL_LLM_API_KEY": "secret123",
        }):
            importlib.reload(local_llm_client)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                local_llm_client.chat("hi")

        self.assertEqual(captured["req"].get_header("Authorization"), "Bearer secret123")

    def test_no_authorization_header_when_api_key_not_configured(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            payload = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
            return _FakeResponse(payload)

        with patch.dict(os.environ, {
            "LOCAL_LLM_BASE_URL": "http://test.invalid/v1",
            "LOCAL_LLM_MODEL": "test-model",
        }, clear=True):
            importlib.reload(local_llm_client)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                local_llm_client.chat("hi")

        self.assertIsNone(captured["req"].get_header("Authorization"))


class TestLocalLlmClientStatus(_ConfiguredTestCase):
    def test_successful_status_is_pretty_printed_json(self):
        payload = json.dumps({"providers": [{"name": "groq", "headroom": 0.99}]}).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = local_llm_client.status()
        self.assertIn('"name": "groq"', result)
        self.assertIn('"headroom": 0.99', result)

    def test_non_json_body_is_returned_as_is(self):
        with patch("urllib.request.urlopen", return_value=_FakeResponse(b"not json")):
            result = local_llm_client.status()
        self.assertEqual(result, "not json")

    def test_status_request_targets_the_status_endpoint(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return _FakeResponse(b"{}")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            local_llm_client.status()
        self.assertEqual(captured["req"].full_url, f"{local_llm_client.DEFAULT_BASE_URL.rstrip('/')}/status")
        self.assertEqual(captured["req"].get_method(), "GET")

    def test_unreachable_backend_returns_labeled_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = local_llm_client.status()
        self.assertIn("[local-llm unavailable]", result)

    def test_401_response_reports_unauthorized(self):
        http_error = urllib.error.HTTPError(
            url="http://example/v1/status", code=401, msg="Unauthorized", hdrs=None, fp=io.BytesIO()
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = local_llm_client.status()
        self.assertIn("[local-llm unauthorized]", result)

    def test_missing_base_url_reports_not_configured_without_any_network_call(self):
        with patch("local_llm_client.DEFAULT_BASE_URL", None):
            with patch("urllib.request.urlopen") as mock_urlopen:
                result = local_llm_client.status()
        mock_urlopen.assert_not_called()
        self.assertIn("[local-llm not configured]", result)

    def test_authorization_header_sent_when_api_key_configured(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["req"] = req
            return _FakeResponse(b"{}")

        with patch("_shared.load_dotenv"), patch.dict(os.environ, {
            "LOCAL_LLM_BASE_URL": "http://test.invalid/v1",
            "LOCAL_LLM_MODEL": "test-model",
            "LOCAL_LLM_API_KEY": "secret123",
        }):
            importlib.reload(local_llm_client)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                local_llm_client.status()
        importlib.reload(local_llm_client)

        self.assertEqual(captured["req"].get_header("Authorization"), "Bearer secret123")


if __name__ == "__main__":
    unittest.main()
