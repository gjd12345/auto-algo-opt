"""Local LLM shim so official EoH can talk to a full-URL OpenAI-compatible host.

Official EoH remote client always POSTs https://{host}/v1/chat/completions.
OpenCode Go uses a path under /zen/go/. This process-local HTTP server accepts
EoH's local-LLM JSON and forwards it without changing EoH source.

Every outbound POST is charged against a shared RequestBudget. EoH's
InterfaceLocalLLM retries each call up to 5x; each retry is a real outbound
attempt, so a budget-rejected call raises BudgetExhausted and the handler
returns 500 {"error":"BudgetExhausted"} WITHOUT any outbound POST.

Requests use the same cancellable subprocess transport as the main loop
(http_post_with_deadline), so a slow trickle cannot outlive the total
deadline, and a global wall clock refuses any further outbound attempt once
the EoH run budget is exhausted.
"""

from __future__ import annotations

import json
import hashlib
import threading
import time
import urllib.error
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline
from agent_skill_loop.contracts import PROBLEM_CVRP
from agent_skill_loop.request_budget import BudgetExhausted, RequestBudget, RequestSlot
from agent_skill_loop.skill_store import _atomic_write_text


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
        wall_seconds: float | None = None,
        problem: str = PROBLEM_CVRP,
    ) -> None:
        self.target_url = target_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.budget = budget
        self.request_log = Path(request_log) if request_log is not None else None
        self._log_lock = threading.Lock()
        self._forward_lock = threading.Lock()
        if self.request_log is not None:
            self.request_log.parent.mkdir(parents=True, exist_ok=True)
        self.wall_deadline = time.monotonic() + float(wall_seconds) if wall_seconds is not None else None
        self.problem = problem
        self.last_error: str | None = None
        self.terminal = False
        self.last_request_index: int | None = None
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
                    purpose = str(payload.get("purpose") or "") or None
                    text = bridge._forward(prompt, purpose=purpose)
                    body = json.dumps({"content": [text], "request_index": bridge.last_request_index}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    if bridge.last_request_index is not None:
                        self.send_header("X-Eoh-Request-Index", str(bridge.last_request_index))
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    err = json.dumps({"error": type(exc).__name__, "error_code": getattr(exc, "error_code", type(exc).__name__)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=lambda: self._server.serve_forever(poll_interval=0.05), daemon=True)
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

    def _remaining_wall(self) -> float | None:
        if self.wall_deadline is None:
            return None
        return self.wall_deadline - time.monotonic()

    def _forward(self, prompt: str, *, purpose: str | None = None) -> str:
        # A local-client retry cannot overlap an unresolved provider request.
        with self._forward_lock:
            return self._forward_serial(prompt, purpose=purpose)

    def _forward_serial(self, prompt: str, *, purpose: str | None = None) -> str:
        # Official EoH's local client retries a failed HTTP response. Once a
        # request has an authentication failure or an unknown result, retries
        # must not create another paid outbound attempt. Returning a bridge
        # error is safe: the upstream retry loop sees the failure, while this
        # gate prevents any further forwarding.
        if self.terminal:
            raise BudgetExhausted(self.last_error or "provider_terminal")
        remaining = self._remaining_wall()
        if remaining is not None and remaining <= 0:
            self.last_error = "wall_time_exhausted"
            self.terminal = True
            raise BudgetExhausted("wall_time_exhausted")
        if purpose not in {"eoh_repair", "eoh_generation", "eoh_probe"}:
            purpose = "eoh_probe" if prompt.strip() == "1+1=?" else "eoh_generation"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2 if purpose == "eoh_repair" else 1.0,
            "max_tokens": 8192 if purpose == "eoh_repair" else 16384,
        }
        if purpose == "eoh_repair":
            # Repair has a machine-checked envelope.  Asking the provider for
            # JSON output prevents a long reasoning preamble from consuming the
            # whole completion and leaving no executable repair document.
            payload["response_format"] = {"type": "json_object"}
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
        slot: RequestSlot | None = None
        if self.budget is not None:
            slot = self.budget.reserve(purpose=purpose, problem=self.problem, model=self.model)
            if slot is None:
                self.last_error = "request_budget_exhausted"
                self.terminal = True
                raise BudgetExhausted("request_budget_exhausted")
            self._log_event(slot.reserved_event)
        started = time.monotonic()
        request_timeout = self.timeout
        if remaining is not None:
            request_timeout = min(self.timeout, max(0.05, remaining))
        try:
            status, raw = http_post_with_deadline(
                self.target_url, headers, json.dumps(payload).encode("utf-8"), request_timeout
            )
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("invalid_completion_object")
            choices = parsed.get("choices") or []
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or not isinstance(choices[0].get("message"), dict):
                raise ValueError("invalid_completion_choices")
            if not isinstance(parsed.get("usage", {}), dict):
                raise ValueError("invalid_completion_usage")
        except ProviderFailure as exc:
            if slot is not None:
                if exc.error_code == "request_deadline":
                    self._record(
                        slot,
                        "killed_unknown",
                        error_code="request_deadline",
                        elapsed_seconds=time.monotonic() - started,
                    )
                elif exc.error_code in {"provider_auth_invalid"} or str(exc.error_code).startswith("http_"):
                    self._record(
                        slot,
                        "http_error",
                        status=exc.status,
                        error_code=exc.error_code,
                        elapsed_seconds=time.monotonic() - started,
                    )
                else:
                    self._record(
                        slot,
                        "connectivity_failed",
                        error_code=exc.error_code,
                        elapsed_seconds=time.monotonic() - started,
                    )
            self.last_error = exc.error_code
            # Only the provider's explicitly retryable classes (for example
            # 429/5xx) may be retried by EoH.  Authentication, protocol and
            # other non-retryable HTTP failures become terminal after the one
            # charged request, so an upstream retry cannot silently duplicate
            # an external call.
            if not (exc.retryable and (exc.status == 429 or isinstance(exc.status, int) and 500 <= exc.status < 600)):
                self.terminal = True
            raise
        except Exception as exc:
            if slot is not None:
                self._record(
                    slot,
                    "connectivity_failed",
                    error_code="provider_connectivity_or_protocol_error",
                    elapsed_seconds=time.monotonic() - started,
                )
            self.last_error = "provider_connectivity_or_protocol_error"
            self.terminal = True
            raise
        choices = parsed.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content") if isinstance(message, dict) else None
        reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
        finish_reason = choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None
        response_metadata = {
            "finish_reason": finish_reason,
            "content_present": isinstance(content, str) and bool(content.strip()),
            "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning.strip()),
            "selected_content_field": "content" if isinstance(content, str) and content.strip() else "reasoning_content" if isinstance(reasoning, str) and reasoning.strip() else None,
            "usage": parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {},
        }
        if isinstance(content, str) and content.strip():
            self._save_exchange(slot, prompt, content, metadata=response_metadata)
            self._record_complete(slot, status, started, parsed, metadata=response_metadata)
            # A retryable transient error may have preceded this successful
            # response; it must not poison the final run status.
            self.last_error = None
            return content
        if isinstance(reasoning, str) and reasoning.strip():
            self._save_exchange(slot, prompt, reasoning, metadata=response_metadata)
            self._record_complete(slot, status, started, parsed, metadata=response_metadata)
            self.last_error = None
            return reasoning
        if slot is not None:
            self._record(
                slot,
                "complete",
                status=status,
                error_code="empty_or_nontext_completion",
                elapsed_seconds=time.monotonic() - started,
            )
        self.last_error = "empty_or_nontext_completion"
        self.terminal = True
        raise RuntimeError("empty_or_nontext_completion")

    def _save_exchange(self, slot: RequestSlot | None, prompt: str, response: str, *, metadata: dict[str, Any] | None = None) -> None:
        if slot is None or self.request_log is None:
            return
        record = {
            "request_index": slot.index, "purpose": slot.purpose,
            "prompt": prompt, "response": response,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
        }
        if metadata:
            record.update(metadata)
        self.last_request_index = slot.index
        try:
            _atomic_write_text(self.request_log.parent / "exchanges" / f"request_{slot.index}.json", json.dumps(record, ensure_ascii=False))
            _atomic_write_text(self.request_log.parent / "latest_exchange.json", json.dumps(record, ensure_ascii=False))
        except OSError:
            self.terminal = True
            self.last_error = "evidence_storage_error"
            self._record(slot, "complete", error_code=self.last_error)
            raise

    def _record_complete(self, slot: RequestSlot | None, status: int, started: float, parsed: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> None:
        if slot is None:
            return
        usage = parsed.get("usage") or {}
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")
        self._record(
            slot,
            "complete",
            status=status,
            error_code=None,
            elapsed_seconds=time.monotonic() - started,
            input_tokens=in_tokens if isinstance(in_tokens, int) else None,
            output_tokens=out_tokens if isinstance(out_tokens, int) else None,
            finish_reason=(metadata or {}).get("finish_reason"),
            selected_content_field=(metadata or {}).get("selected_content_field"),
        )
