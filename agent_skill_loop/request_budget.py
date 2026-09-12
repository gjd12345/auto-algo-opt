"""Real HTTP request budget used by the production EoH bridge.

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

    @property
    def remaining(self) -> int | None:
        with self._lock:
            return None if self.max_requests is None else max(0, self.max_requests - self._used)

    def consume_external(
        self,
        count: int,
        *,
        purpose: str,
        problem: str,
        model: str | None = None,
        records: list[dict[str, Any]] | None = None,
    ) -> None:
        """Account for requests already made by a supervised child process.

        The child receives ``remaining`` as its hard cap.  This method only
        reconciles its durable summary into the parent ledger; it never sends
        a request or invents token usage.
        """
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("external_request_count_invalid")
        if records is not None:
            if len(records) != count:
                raise ValueError("external_request_records_mismatch")
        with self._lock:
            if self.max_requests is not None and self._used + count > self.max_requests:
                raise BudgetExhausted("external_request_budget_overrun")
            for record in records or [{} for _ in range(count)]:
                record_purpose = record.get("purpose", purpose)
                record_problem = record.get("problem", problem)
                record_model = record.get("model", model)
                self._used += 1
                slot = RequestSlot(self._used, record_purpose, record_problem, None, record_model, state="external_completed")
                self.events.append(self._make_event(
                    slot,
                    "external_completed",
                    status=record.get("status"),
                    error_code=record.get("error_code"),
                    elapsed_seconds=record.get("elapsed_seconds"),
                    input_tokens=record.get("input_tokens"),
                    output_tokens=record.get("output_tokens"),
                    finish_reason=record.get("finish_reason"),
                    selected_content_field=record.get("selected_content_field"),
                ))

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
            "finish_reason": fields.get("finish_reason"),
            "selected_content_field": fields.get("selected_content_field"),
        }
