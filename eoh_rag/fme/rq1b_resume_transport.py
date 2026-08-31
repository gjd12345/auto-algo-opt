"""Bounded continuation transport for an interrupted RQ1b stream run."""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Any

from eoh_rag.fme.online_adapters import ProviderFailure, digest
from eoh_rag.fme.rq1b_transport import DurableTransport


class RemainingTransport(DurableTransport):
    """Resume only requests with no successfully delivered complete response.

    ``before_request`` is an optional controller callback.  It is called before
    every HTTP attempt and must reserve the attempt or raise; no request is
    issued when the callback rejects the reservation.
    """

    def __init__(self, protocol: Mapping[str, Any], journal: Any, *,
                 before_request: Callable[[dict[str, Any]], Any] | None = None) -> None:
        super().__init__(protocol, journal)
        self.before_request = before_request
        self.logical_id: str | None = None

    def set_logical_id(self, logical_id: str) -> None:
        if not isinstance(logical_id, str) or not logical_id:
            raise ValueError("logical_id_required")
        self.logical_id = logical_id

    @staticmethod
    def _wait_for(global_attempt: int) -> int:
        if global_attempt == 1:
            return 0
        if global_attempt in {2, 5, 8}:
            return 2
        if global_attempt in {3, 6, 9}:
            return 4
        if global_attempt == 4:
            return 10
        if global_attempt == 7:
            return 30
        raise ValueError("global_http_attempt_out_of_range")

    @staticmethod
    def _is_incomplete_json_response(exc: ProviderFailure, usage: list[dict[str, Any]]) -> bool:
        if exc.retryable or not usage:
            return False
        receipt = usage[-1]
        return receipt.get("http_status") == 200 and receipt.get("error_code") == "JSONDecodeError"

    def request_remaining(self, prompt: str, *, purpose: str, problem: str,
                          prior_http_attempts: int = 0) -> str:
        if not isinstance(prior_http_attempts, int) or not 0 <= prior_http_attempts <= 9:
            raise ValueError("prior_http_attempts_out_of_range")
        if not self.logical_id or self.before_request is None:
            raise RuntimeError('continuation_budget_gate_required')
        logical_id = self.logical_id
        for offset in range(9 - prior_http_attempts):
            global_attempt = prior_http_attempts + offset + 1
            delay = self._wait_for(global_attempt)
            inner=((global_attempt-1)%3)+1
            if inner==1:
                self.journal.append('recovery_started',{'cycle':(global_attempt-1)//3+1,
                    'delay_seconds':delay,'model':self.model,'purpose':purpose,'problem':problem,
                    'prompt_hash':digest(prompt),'boundary':'authorized_same_request_transport_continuation'})
            else:
                self.journal.append('transport_retry_scheduled',{'model':self.model,'purpose':purpose,
                    'prompt_hash':digest(prompt),'failed_transport_attempt':inner-1,'delay_seconds':delay,
                    'error_code':self.usage[-1].get('error_code'),'boundary':'no_complete_response_was_delivered'})
            reservation = {
                "logical_id": logical_id,
                "global_attempt": global_attempt,
                "old_attempts": prior_http_attempts,
                "cost": 1,
                "model": self.model,
                "purpose": purpose,
                "problem": problem,
                "prompt_hash": digest(prompt),
                "delay_seconds": delay,
            }
            if self.before_request is not None:
                self.before_request(dict(reservation))
            self.journal.append("resume_http_attempt_reserved", reservation)
            if delay:
                time.sleep(delay)
            try:
                response = self._request_once(
                    prompt, purpose=purpose, problem=problem,
                    # Preserve the base receipt's per-cycle compatibility:
                    # attempts are 1..3 within each resumed cycle.
                    transport_attempt=((global_attempt - 1) % 3) + 1)
            except ProviderFailure as exc:
                retryable = exc.retryable or self._is_incomplete_json_response(exc, self.usage)
                self.journal.append("resume_http_attempt_result", {
                    **reservation, "ok": False, "retryable": retryable,
                    "error_code": self.usage[-1].get("error_code") if self.usage else exc.error_code,
                })
                if not retryable or global_attempt == 9:
                    raise
                continue
            ordinal = self._ordinal
            self._checkpoint(ordinal, prompt, response, purpose=purpose, problem=problem)
            self._ordinal += 1
            self.journal.append("checkpoint_saved", {
                "ordinal": ordinal,
                "path": f"request-{ordinal:06d}.json",
                "prompt_hash": digest(prompt),
                "response_hash": digest(response),
                "request_spec_hash": digest(self._request_spec(prompt, purpose, problem)),
            })
            self.journal.append("resume_http_attempt_result", {**reservation, "ok": True})
            return response
        raise ProviderFailure("http_attempt_budget_exhausted")

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        return self.request_remaining(prompt, purpose=purpose, problem=problem, prior_http_attempts=0)
