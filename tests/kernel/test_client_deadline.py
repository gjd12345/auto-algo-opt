from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent_skill_loop import client as client_mod
from agent_skill_loop.client import LiveTransport, ProviderFailure, _open_url_with_deadline, http_post_with_deadline


class _SlowHandler(BaseHTTPRequestHandler):
    payload = b'{"choices":[{"message":{"content":"' + (b"x" * 400) + b'"}}]}'
    chunks_sent = 0
    finished = False
    lock = threading.Lock()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        try:
            for index in range(0, len(self.payload), 8):
                self.wfile.write(self.payload[index : index + 8])
                self.wfile.flush()
                with self.lock:
                    type(self).chunks_sent += 1
                time.sleep(0.2)
            with self.lock:
                type(self).finished = True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _FastHandler(BaseHTTPRequestHandler):
    payload = b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}'

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _start_server(handler_cls) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_open_url_with_deadline_cancels_slow_body():
    _SlowHandler.chunks_sent = 0
    _SlowHandler.finished = False
    server = _start_server(_SlowHandler)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        request = urllib.request.Request(
            url,
            data=b'{"model":"x"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        started = time.monotonic()
        with pytest.raises(ProviderFailure) as raised:
            _open_url_with_deadline(request, 0.45)
        elapsed = time.monotonic() - started
        assert raised.value.error_code == "request_deadline"
        assert elapsed < 2.5
        assert _SlowHandler.finished is False
        assert _SlowHandler.chunks_sent < 20
    finally:
        server.shutdown()
        server.server_close()


def test_open_url_with_deadline_allows_fast_body():
    server = _start_server(_FastHandler)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        request = urllib.request.Request(
            url,
            data=b'{"model":"x"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        status, body = _open_url_with_deadline(request, 5.0)
        assert status == 200
        assert json.loads(body.decode("utf-8"))["choices"][0]["message"]["content"] == "ok"
    finally:
        server.shutdown()
        server.server_close()


class _HangHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        time.sleep(30)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_http_post_kills_hanging_request():
    server = _start_server(_HangHandler)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        started = time.monotonic()
        with pytest.raises(ProviderFailure) as raised:
            http_post_with_deadline(url, {"Content-Type": "application/json"}, b"{}", 0.5)
        elapsed = time.monotonic() - started
        assert raised.value.error_code == "request_deadline"
        assert elapsed < 3.0
    finally:
        server.shutdown()
        server.server_close()


def test_live_transport_uses_deadline_helper(monkeypatch):
    seen: dict[str, float] = {}

    def fake_post(url, headers, data, timeout, max_bytes=4 * 1024 * 1024):
        seen["timeout"] = timeout
        return 200, b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":3,"completion_tokens":4}}'

    monkeypatch.setattr(client_mod, "http_post_with_deadline", fake_post)
    monkeypatch.setenv("MODEL_ROUTER_API_KEY", "test-key")
    transport = LiveTransport(
        "deepseek-v4-flash",
        timeout=90.0,
        endpoint="https://opencode.ai/zen/go/v1/chat/completions",
    )
    text = transport.request("prompt", purpose="generation", problem="cvrp_construct", timeout=12.0)
    assert text == "ok"
    assert seen["timeout"] == 12.0
    assert transport.usage[-1].input_tokens == 3
    assert transport.usage[-1].output_tokens == 4
    assert transport.usage[-1].model == "deepseek-v4-flash"
