"""Shared provider errors, environment loading and deadline-bound HTTP primitives."""

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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class ProviderFailure(RuntimeError):
    def __init__(self, error_code: str, status: int | None = None, *, retryable: bool = False) -> None:
        self.error_code = error_code
        self.status = status
        self.retryable = retryable
        super().__init__(error_code)




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
