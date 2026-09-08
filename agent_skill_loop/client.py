"""Injectable model client. Fixture and live share one request() contract."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
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
    model: str | None = None


class FixtureTransport:
    """Scripted responses. Never opens a network connection."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.timeouts: list[float | None] = []
        self.usage: list[UsageReceipt] = []

    def request(self, prompt: str, *, purpose: str, problem: str, timeout: float | None = None) -> str:
        if purpose != "generation":
            raise ProviderFailure("unexpected_purpose")
        self.prompts.append(prompt)
        self.timeouts.append(timeout)
        if not self._responses:
            raise ProviderFailure("fixture_exhausted")
        text = self._responses.pop(0)
        self.usage.append(UsageReceipt(
            purpose, problem, _hash(prompt), True, None, None, None, 0.0, False, None,
        ))
        return text


class AuthFailTransport:
    def request(self, prompt: str, *, purpose: str, problem: str, timeout: float | None = None) -> str:
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


_MAX_BODY_BYTES = 4 * 1024 * 1024
_READ_CHUNK = 8 * 1024


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return False
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return True
        text = str(reason).lower()
        if "timed out" in text or "timeout" in text:
            return True
    return False


def _socket_from_response(response: object) -> Any:
    fp = getattr(response, "fp", None)
    if fp is None:
        return None
    raw = getattr(fp, "raw", None)
    sock = getattr(raw, "_sock", None) if raw is not None else None
    if sock is not None and hasattr(sock, "settimeout"):
        return sock
    if hasattr(fp, "settimeout"):
        return fp
    return None


def _close_response(response: Any) -> None:
    if response is None:
        return
    sock = _socket_from_response(response)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
    try:
        response.close()
    except Exception:
        pass


def _read_some(response: Any, nbytes: int) -> bytes:
    """Read at most one underlying recv when possible.

    HTTPResponse.read(n) loops until n bytes or EOF, so a slow trickle can
    outlive the remaining budget even with a socket timeout.
    """
    if nbytes <= 0:
        return b""
    if getattr(response, "chunked", False):
        return response.read(1)
    fp = getattr(response, "fp", None)
    read1 = getattr(fp, "read1", None) if fp is not None else None
    if callable(read1):
        data = read1(nbytes)
        if data:
            length = getattr(response, "length", None)
            if isinstance(length, int):
                response.length = max(0, length - len(data))
        return data
    return response.read(1)


def _read_response_until_deadline(response: Any, max_bytes: int, deadline: float) -> bytes:
    chunks: list[bytes] = []
    total = 0
    expected = getattr(response, "length", None)
    sock = _socket_from_response(response)
    while total < max_bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("request_deadline")
        if isinstance(expected, int) and total >= expected:
            break
        if sock is not None:
            try:
                sock.settimeout(remaining)
            except OSError:
                pass
        want = min(_READ_CHUNK, max_bytes - total)
        if isinstance(expected, int):
            want = min(want, max(0, expected - total))
        try:
            chunk = _read_some(response, want)
        except TimeoutError:
            raise TimeoutError("request_deadline") from None
        except OSError as exc:
            if _is_timeout(exc) or deadline - time.monotonic() <= 0:
                raise TimeoutError("request_deadline") from exc
            raise
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def _reraise_worker_error(exc: BaseException) -> None:
    if isinstance(exc, urllib.error.HTTPError):
        raise exc
    if isinstance(exc, ProviderFailure):
        raise exc
    if _is_timeout(exc):
        raise ProviderFailure("request_deadline", retryable=True) from exc
    if isinstance(exc, (OSError, ValueError, TypeError, KeyError, IndexError)):
        raise ProviderFailure("provider_connectivity_or_protocol_error", retryable=True) from exc
    raise exc


def _open_url_with_deadline(
    request: urllib.request.Request,
    timeout: float,
    *,
    max_bytes: int = _MAX_BODY_BYTES,
) -> tuple[int, bytes]:
    """Open and read the HTTP body under a total deadline, not per-recv timeout.

    urlopen(timeout=...) only bounds each blocking syscall. This function also
    cancels the in-flight response when the whole request exceeds `timeout`.
    """
    if timeout <= 0:
        raise ProviderFailure("request_deadline", retryable=True)
    deadline = time.monotonic() + float(timeout)
    box: dict[str, Any] = {}
    done = threading.Event()

    def work() -> None:
        response = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("request_deadline")
            response = urllib.request.urlopen(request, timeout=remaining)
            box["response"] = response
            body = _read_response_until_deadline(response, max_bytes, deadline)
            box["result"] = (int(response.status), body)
        except BaseException as exc:
            box["error"] = exc
        finally:
            _close_response(response)
            done.set()

    thread = threading.Thread(target=work, name="agent-skill-http", daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, deadline - time.monotonic()))
    if thread.is_alive() or not done.is_set():
        _close_response(box.get("response"))
        raise ProviderFailure("request_deadline", retryable=True)
    if "result" in box:
        return box["result"]
    error = box.get("error")
    if error is not None:
        _reraise_worker_error(error)
    raise ProviderFailure("request_deadline", retryable=True)


def _kill_process(proc: subprocess.Popen[bytes]) -> None:
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=2.0)
    except (OSError, subprocess.TimeoutExpired):
        pass


def http_post_with_deadline(
    url: str,
    headers: dict[str, str],
    data: bytes,
    timeout: float,
    *,
    max_bytes: int = _MAX_BODY_BYTES,
) -> tuple[int, bytes]:
    """POST in a child process so a hung connect/read can be killed at the deadline."""
    if timeout <= 0:
        raise ProviderFailure("request_deadline", retryable=True)
    spec = {
        "url": url,
        "headers": headers,
        "body_b64": base64.b64encode(data).decode("ascii"),
        "timeout": float(timeout),
        "max_bytes": int(max_bytes),
    }
    package_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package_root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent_skill_loop.http_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=tempfile.gettempdir(),
        env=env,
    )
    try:
        stdout, _ = proc.communicate(json.dumps(spec).encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process(proc)
        raise ProviderFailure("request_deadline", retryable=True) from None
    if proc.poll() is None:
        _kill_process(proc)
        raise ProviderFailure("request_deadline", retryable=True)
    try:
        parsed = json.loads((stdout or b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ProviderFailure("provider_connectivity_or_protocol_error", retryable=True) from None
    if parsed.get("ok") is True:
        return int(parsed["status"]), base64.b64decode(parsed["body_b64"])
    error_code = parsed.get("error_code") or "provider_connectivity_or_protocol_error"
    status = parsed.get("status")
    retryable = error_code == "request_deadline" or (
        isinstance(status, int) and status in {408, 429, 500, 502, 503, 504}
    )
    raise ProviderFailure(str(error_code), status if isinstance(status, int) else None, retryable=retryable)


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

    def request(self, prompt: str, *, purpose: str, problem: str, timeout: float | None = None) -> str:
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
        if host.endswith("opencode.ai"):
            payload["thinking"] = {"type": "disabled"}
            payload["reasoning"] = {"effort": "none"}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-skill-loop/0908",
        }
        if host.endswith("opencode.ai"):
            headers["x-opencode-session"] = self.session_id
        started = time.monotonic()
        receipt_error: str | None = None
        content = ""
        status = None
        in_tokens = out_tokens = None
        effective_timeout = self.timeout if timeout is None else min(self.timeout, float(timeout))
        try:
            status, raw = http_post_with_deadline(
                self.endpoint, headers, json.dumps(payload).encode("utf-8"), effective_timeout
            )
            parsed = json.loads(raw.decode("utf-8"))
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
                in_tokens, out_tokens, time.monotonic() - started, True, self.model,
            ))
