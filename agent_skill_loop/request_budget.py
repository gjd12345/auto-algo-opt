"""Unified real HTTP request budget shared by LiveTransport and the EoH bridge.

Every outbound provider POST must reserve a slot before it is sent. EoH's
InterfaceLocalLLM retries each call up to 5x, and every retry is a real
outbound attempt, so the budget is enforced at our bridge/transport layer
(never inside the official eoh package).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


class BudgetExhausted(RuntimeError):
    """Raised when a reserve() is attempted past the budget."""


@dataclass
class RequestSlot:
    index: int
    purpose: str
    problem: str
    attempt: int | None
    model: str | None
    state: str = "reserved"
    elapsed_seconds: float | None = None
    status: int | None = None
    error_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reserved_event: dict[str, Any] | None = field(default=None, repr=False)


class RequestBudget:
    """Thread-safe counter of real outbound HTTP attempts.

    ``reserve`` is the only gate: it returns ``None`` once ``used >=
    max_requests`` (or never, when ``max_requests`` is ``None``). Every
    reservation and every terminal state is appended to ``events``.
    """

    def __init__(self, max_requests: int | None) -> None:
        self.max_requests = max_requests
        self._lock = threading.Lock()
        self._used = 0
        self._rejected = 0
        self.events: list[dict[str, Any]] = []

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def rejected(self) -> int:
        with self._lock:
            return self._rejected

    def reserve(
        self,
        *,
        purpose: str,
        problem: str,
        attempt: int | None = None,
        model: str | None = None,
    ) -> RequestSlot | None:
        with self._lock:
            if self.max_requests is not None and self._used >= self.max_requests:
                self._rejected += 1
                return None
            self._used += 1
            slot = RequestSlot(
                index=self._used,
                purpose=purpose,
                problem=problem,
                attempt=attempt,
                model=model,
            )
        event = self._make_event(slot, "reserved")
        slot.reserved_event = event
        with self._lock:
            self.events.append(event)
        return slot

    def add_event(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        event = self._make_event(slot, state, **fields)
        with self._lock:
            self.events.append(event)
        return event

    def finish(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        if state == "killed_unknown":
            # A deadline-canceled request never produced token counts.
            fields["input_tokens"] = None
            fields["output_tokens"] = None
        slot.state = state
        if "elapsed_seconds" in fields:
            slot.elapsed_seconds = fields["elapsed_seconds"]
        if "status" in fields:
            slot.status = fields["status"]
        if "error_code" in fields:
            slot.error_code = fields["error_code"]
        if "input_tokens" in fields:
            slot.input_tokens = fields["input_tokens"]
        if "output_tokens" in fields:
            slot.output_tokens = fields["output_tokens"]
        if "model" in fields:
            slot.model = fields["model"]
        return self.add_event(slot, state, **fields)

    def _make_event(self, slot: RequestSlot, state: str, **fields: Any) -> dict[str, Any]:
        return {
            "state": state,
            "purpose": slot.purpose,
            "problem": slot.problem,
            "attempt": slot.attempt,
            "index": slot.index,
            "model": fields.get("model", slot.model),
            "elapsed_seconds": fields.get("elapsed_seconds", slot.elapsed_seconds),
            "status": fields.get("status", slot.status),
            "error_code": fields.get("error_code", slot.error_code),
            "input_tokens": fields.get("input_tokens", slot.input_tokens),
            "output_tokens": fields.get("output_tokens", slot.output_tokens),
        }