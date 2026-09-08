"""Local LLM shim so official EoH can talk to a full-URL OpenAI-compatible host.

Official EoH remote client always POSTs https://{host}/v1/chat/completions.
OpenCode Go uses a path under /zen/go/. This process-local HTTP server accepts
EoH's local-LLM JSON and forwards it without changing EoH source.
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class OpenAIPathBridge:
    def __init__(self, target_url: str, api_key: str, model: str, *, timeout: float = 180.0) -> None:
        self.target_url = target_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.session_id = str(uuid.uuid4())
        self._server: ThreadingHTTPServer | None = None
        host = urlsplit(target_url).hostname or ""
        self._opencode = host.endswith("opencode.ai")

    @property
    def local_url(self) -> str:
        if self._server is None:
            raise RuntimeError("bridge_not_started")
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/completions"

    def start(self) -> str:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    prompt = str(payload.get("prompt") or "")
                    text = bridge._forward(prompt)
                    body = json.dumps({"content": [text]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    err = json.dumps({"error": type(exc).__name__}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        return self.local_url

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def _forward(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1.0,
            "max_tokens": 16384,
        }
        if self._opencode:
            payload["thinking"] = {"type": "disabled"}
            payload["reasoning"] = {"effort": "none"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "eoh-frozen-bridge/0908",
        }
        if self._opencode:
            headers["x-opencode-session"] = self.session_id
        request = Request(
            self.target_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            parsed = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
        choices = parsed.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        if isinstance(content, str) and content.strip():
            return content
        reasoning = choices[0].get("message", {}).get("reasoning_content") if choices else None
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning
        raise RuntimeError("empty_or_nontext_completion")
