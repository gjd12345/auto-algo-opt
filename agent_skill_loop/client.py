"""Injectable model client. Fixture and live share one request() contract."""

from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ProviderFailure(RuntimeError):
    def __init__(self, error_code: str, status: int | None = None, *, retryable: bool = False) -> None:
        self.error_code = error_code
        self.status = status
        self.retryable = retryable
        super().__init__(error_code)


@dataclass
class UsageReceipt:
    purpose: str
    problem: str
    prompt_hash: str
    ok: bool
    error_code: str | None
    input_tokens: int | None
    output_tokens: int | None
    elapsed_seconds: float
    network_request: bool


class FixtureTransport:
    """Scripted responses. Never opens a network connection."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.usage: list[UsageReceipt] = []

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        if purpose != "generation":
            raise ProviderFailure("unexpected_purpose")
        self.prompts.append(prompt)
        if not self._responses:
            raise ProviderFailure("fixture_exhausted")
        text = self._responses.pop(0)
        self.usage.append(UsageReceipt(purpose, problem, _hash(prompt), True, None, None, None, 0.0, False))
        return text


class AuthFailTransport:
    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        raise ProviderFailure("provider_auth_invalid", 401, retryable=False)


def load_local_env(path: Path | None = None) -> None:
    """Load repo .env without overriding variables already in the process."""
    env_path = path or (Path(__file__).resolve().parents[1] / ".env")
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _hash(prompt: str) -> str:
    import hashlib
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class LiveTransport:
    """OpenAI-compatible chat completions. network_retries is always 0 for v1."""

    def __init__(self, model: str, *, timeout: float = 90.0, endpoint: str | None = None, api_key_env: str = "MODEL_ROUTER_API_KEY") -> None:
        self.model = model
        self.timeout = timeout
        self.endpoint = endpoint or os.environ.get(
            "MODEL_ROUTER_API_ENDPOINT",
            "https://model-router.edu-aliyun.com/v1/chat/completions",
        )
        self.api_key_env = api_key_env
        self.session_id = str(uuid.uuid4())
        self.usage: list[UsageReceipt] = []

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        if purpose != "generation":
            raise ProviderFailure("unexpected_purpose")
        api_key = os.environ.get(self.api_key_env, "")
        if not api_key or not self.model:
            raise ProviderFailure("missing_model_or_key")
        host = urlsplit(self.endpoint).hostname or ""
        allowed = {"model-router.edu-aliyun.com", "opencode.ai", "api.deepseek.com"}
        if urlsplit(self.endpoint).scheme != "https" or host not in allowed:
            raise ProviderFailure("provider_endpoint_outside_authorized_host")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0,
            "max_tokens": 16384,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-skill-loop/0908",
        }
        if host.endswith("opencode.ai"):
            headers["x-opencode-session"] = self.session_id
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.monotonic()
        receipt_error: str | None = None
        content = ""
        status = None
        in_tokens = out_tokens = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
                parsed = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
            choices = parsed.get("choices") or []
            content = choices[0].get("message", {}).get("content") if choices else None
            usage = parsed.get("usage") or {}
            in_tokens = usage.get("prompt_tokens")
            out_tokens = usage.get("completion_tokens")
            if not isinstance(content, str) or not content.strip():
                reasoning = choices[0].get("message", {}).get("reasoning_content") if choices else None
                if isinstance(reasoning, str) and reasoning.strip():
                    content = reasoning
                else:
                    raise ProviderFailure("empty_or_nontext_completion", status)
            return content
        except urllib.error.HTTPError as exc:
            receipt_error = "provider_auth_invalid" if exc.code in {401, 403} else f"http_{exc.code}"
            raise ProviderFailure(receipt_error, exc.code, retryable=exc.code in {408, 429, 500, 502, 503, 504}) from None
        except ProviderFailure as exc:
            receipt_error = exc.error_code
            raise
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            receipt_error = "provider_connectivity_or_protocol_error"
            raise ProviderFailure(receipt_error, retryable=True) from None
        finally:
            self.usage.append(UsageReceipt(
                purpose, problem, _hash(prompt), receipt_error is None, receipt_error,
                in_tokens, out_tokens, time.monotonic() - started, True,
            ))
