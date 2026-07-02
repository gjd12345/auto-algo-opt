"""Tests for eoh_rag.llm.client and eoh_rag.llm.utils."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from eoh_rag.llm.client import chat_completion, normalize_endpoint
from eoh_rag.llm.utils import extract_code_block


class TestNormalizeEndpoint:
    def test_bare_domain(self):
        assert normalize_endpoint("api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"

    def test_with_https(self):
        assert normalize_endpoint("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"

    def test_with_full_path(self):
        assert normalize_endpoint("https://api.example.com/v1/chat/completions") == "https://api.example.com/v1/chat/completions"

    def test_with_custom_path(self):
        assert normalize_endpoint("https://api.example.com/custom/endpoint") == "https://api.example.com/custom/endpoint"

    def test_domain_with_slash(self):
        assert normalize_endpoint("api.example.com/v1/chat/completions") == "https://api.example.com/v1/chat/completions"

    def test_empty(self):
        assert normalize_endpoint("") == ""

    def test_trailing_slash(self):
        assert normalize_endpoint("api.deepseek.com/") == "https://api.deepseek.com/v1/chat/completions"


class TestChatCompletion:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="API key not provided"):
            chat_completion([{"role": "user", "content": "hi"}], endpoint="x.com")

    def test_raises_without_endpoint(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_ENDPOINT", raising=False)
        with pytest.raises(RuntimeError, match="endpoint not provided"):
            chat_completion([{"role": "user", "content": "hi"}], api_key="sk-xxx")

    @patch("eoh_rag.llm.client.urllib.request.urlopen")
    def test_success(self, mock_urlopen, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_ENDPOINT", raising=False)

        response_body = json.dumps({
            "choices": [{"message": {"content": "hello world"}}]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = chat_completion(
            [{"role": "user", "content": "hi"}],
            api_key="sk-test",
            endpoint="api.test.com",
            model="test-model",
        )
        assert result == "hello world"

    @patch("eoh_rag.llm.client.urllib.request.urlopen")
    def test_retries_on_failure(self, mock_urlopen, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_ENDPOINT", raising=False)

        mock_urlopen.side_effect = [
            TimeoutError("timeout"),
            TimeoutError("timeout"),
        ]

        with pytest.raises(RuntimeError, match="failed after 2 attempts"):
            chat_completion(
                [{"role": "user", "content": "hi"}],
                api_key="sk-test",
                endpoint="api.test.com",
                max_retries=2,
            )
        assert mock_urlopen.call_count == 2


class TestExtractCodeBlock:
    def test_go_block(self):
        text = "Here is code:\n```go\nfunc main() {}\n```\ndone"
        assert extract_code_block(text) == "func main() {}"

    def test_no_lang_specified(self):
        text = "```go\nfunc Foo() int { return 1 }\n```"
        assert extract_code_block(text, lang="go") == "func Foo() int { return 1 }"

    def test_no_match(self):
        text = "just plain text"
        assert extract_code_block(text) is None

    def test_python_block(self):
        text = "```python\ndef foo(): pass\n```"
        assert extract_code_block(text, lang="python") == "def foo(): pass"
