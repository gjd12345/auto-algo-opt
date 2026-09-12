"""OpenAI-compatible requester for Plan and Evaluate roles."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline
from agent_skill_loop.request_budget import RequestBudget


def provider_url(endpoint: str) -> str:
    value = endpoint if "://" in endpoint else f"https://{endpoint}"
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


class RoleClient:
    def __init__(self, endpoint: str, *, model: str, api_key: str, budget: RequestBudget,
                 deadline: float, request_log: Path | None = None) -> None:
        self.endpoint = provider_url(endpoint)
        self.model = model
        self.api_key = api_key
        self.budget = budget
        self.deadline = deadline
        self.request_log = Path(request_log) if request_log else None
        if self.request_log:
            self.request_log.parent.mkdir(parents=True, exist_ok=True)

    def request(self, prompt: str, *, purpose: str, problem: str, timeout: float | None = None) -> str:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderFailure("wall_time_exhausted")
        if not self.api_key or not self.model:
            raise ProviderFailure("provider_auth_invalid")
        slot = self.budget.reserve(purpose=purpose, problem=problem, model=self.model)
        if slot is None:
            raise ProviderFailure("request_budget_exhausted")
        started = time.monotonic()
        status: int | None = None
        input_tokens = output_tokens = None
        error_code: str | None = None
        try:
            parsed_url = urlsplit(self.endpoint)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ProviderFailure("provider_endpoint_invalid")
            # Both workflow roles have a strict JSON contract.  DeepSeek's
            # OpenAI-compatible endpoint supports JSON mode, which prevents a
            # long free-form continuation from consuming the whole completion
            # budget before the contract object is emitted.
            payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2 if purpose == "evaluate" else 1.0,
                       "max_tokens": 8192 if purpose == "evaluate" else 4096,
                       "response_format": {"type": "json_object"}}
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                       "User-Agent": "agent-skill-loop-3plus1/1"}
            status, raw = http_post_with_deadline(
                self.endpoint, headers, json.dumps(payload).encode("utf-8"),
                min(timeout or 90.0, max(0.05, remaining)),
            )
            response = json.loads(raw.decode("utf-8"))
            if not isinstance(response, dict) or not isinstance(response.get("choices"), list) or not response["choices"]:
                raise ProviderFailure("provider_connectivity_or_protocol_error")
            message = response["choices"][0].get("message")
            if not isinstance(message, dict):
                raise ProviderFailure("provider_connectivity_or_protocol_error")
            content = message.get("content") or message.get("reasoning_content")
            if not isinstance(content, str) or not content.strip():
                raise ProviderFailure("empty_or_nontext_completion", status)
            usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
            input_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None
            output_tokens = usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None
            self.budget.finish(slot, "complete", status=status, elapsed_seconds=time.monotonic() - started,
                               model=self.model, input_tokens=input_tokens, output_tokens=output_tokens)
            self._log({"purpose": purpose, "problem": problem, "model": self.model, "state": "complete",
                       "request_index": slot.index, "prompt_sha256": _sha(prompt),
                       "input_tokens": input_tokens, "output_tokens": output_tokens,
                       "elapsed_seconds": time.monotonic() - started})
            return content
        except ProviderFailure as exc:
            error_code = exc.error_code
            state = "killed_unknown" if exc.error_code in {"request_deadline", "wall_time_exhausted"} else "provider_failed"
            self.budget.finish(slot, state, status=exc.status, error_code=exc.error_code,
                               elapsed_seconds=time.monotonic() - started, model=self.model)
            self._log({"purpose": purpose, "problem": problem, "model": self.model, "state": state,
                       "request_index": slot.index, "prompt_sha256": _sha(prompt), "error_code": error_code,
                       "input_tokens": None, "output_tokens": None,
                       "elapsed_seconds": time.monotonic() - started})
            raise
        except Exception:
            error_code = "provider_connectivity_or_protocol_error"
            self.budget.finish(slot, "provider_failed", status=status, error_code=error_code,
                               elapsed_seconds=time.monotonic() - started, model=self.model)
            self._log({"purpose": purpose, "problem": problem, "model": self.model, "state": "provider_failed",
                       "request_index": slot.index, "prompt_sha256": _sha(prompt), "error_code": error_code,
                       "input_tokens": None, "output_tokens": None,
                       "elapsed_seconds": time.monotonic() - started})
            raise ProviderFailure(error_code) from None

    def _log(self, payload: dict[str, Any]) -> None:
        if self.request_log is None:
            return
        with self.request_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n")


def _sha(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
