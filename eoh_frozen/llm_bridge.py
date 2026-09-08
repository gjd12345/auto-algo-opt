"""Local LLM shim so official EoH can talk to a full-URL OpenAI-compatible host.

Official EoH remote client always POSTs https://{host}/v1/chat/completions.
OpenCode Go uses a path under /zen/go/. This process-local HTTP server accepts
EoH's local-LLM JSON and forwards it without changing EoH source.

Every outbound POST is charged against a shared RequestBudget. EoH's
InterfaceLocalLLM retries each call up to 5x; each retry is a real outbound
attempt, so a budget-rejected call raises BudgetExhausted and the handler
returns 500 {"error":"BudgetExhausted"} WITHOUT any outbound POST.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from agent_skill_loop.contracts import PROBLEM_CVRP
from agent_skill_loop.request_budget import BudgetExhausted, RequestBudget, RequestSlot


def _is_timeout(exc: BaseException) -> bool:
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


class OpenAIPathBridge:
    def __init__(
        self,
        target_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 180.0,
        budget: RequestBudget | None = None,
        request_log: Path | None = None,
    ) -> None:
        self.target_url = target_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.budget = budget
        self.request_log = Path(request_log) if request_log is not None else None
        self._log_lock = threading.Lock()
        if self.request_log is not None:
            self.request_log.parent.mkdir(parents=True, exist_ok=True)
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

    def _log_event(self, event: dict[str, Any] | None) -> None:
        if event is None or self.request_log is None:
            return
        with self._log_lock:
            with self.request_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _record(self, slot: RequestSlot, state: str, **fields: Any) -> None:
        if self.budget is None:
            return
        event = self.budget.finish(slot, state, **fields)
        self._log_event(event)

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
        slot: RequestSlot | None = None
        if self.budget is not None:
            slot = self.budget.reserve(purpose="eoh_generation", problem=PROBLEM_CVRP, model=self.model)
            if slot is None:
                raise BudgetExhausted("request_budget_exhausted")
            self._log_event(slot.reserved_event)
        started = time.monotonic()
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = int(response.status)
                parsed = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_code = "provider_auth_invalid" if exc.code in {401, 403} else f"http_{exc.code}"
            if slot is not None:
                self._record(
                    slot,
                    "http_error",
                    status=exc.code,
                    error_code=error_code,
                    elapsed_seconds=time.monotonic() - started,
                )
            raise
        except Exception as exc:
            if slot is not None:
                if _is_timeout(exc):
                    self._record(
                        slot,
                        "killed_unknown",
                        error_code="request_deadline",
                        elapsed_seconds=time.monotonic() - started,
                    )
                else:
                    self._record(
                        slot,
                        "connectivity_failed",
                        error_code="provider_connectivity_or_protocol_error",
                        elapsed_seconds=time.monotonic() - started,
                    )
            raise
        choices = parsed.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        if isinstance(content, str) and content.strip():
            if slot is not None:
                self._record(
                    slot,
                    "complete",
                    status=status,
                    error_code=None,
                    elapsed_seconds=time.monotonic() - started,
                )
            return content
        reasoning = choices[0].get("message", {}).get("reasoning_content") if choices else None
        if isinstance(reasoning, str) and reasoning.strip():
            if slot is not None:
                self._record(
                    slot,
                    "complete",
                    status=status,
                    error_code=None,
                    elapsed_seconds=time.monotonic() - started,
                )
            return reasoning
        if slot is not None:
            self._record(
                slot,
                "complete",
                status=status,
                error_code="empty_or_nontext_completion",
                elapsed_seconds=time.monotonic() - started,
            )
        raise RuntimeError("empty_or_nontext_completion")