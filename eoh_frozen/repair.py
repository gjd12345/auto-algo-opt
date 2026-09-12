"""Bounded repair adapter for the pinned official EoH engine.

The adapter deliberately sits at the private ``EOH._build_offspring`` boundary.
It never replaces parent selection, operators, population management, or the
isolated evaluator.  A failed generated offspring may receive at most one
repair request and is then evaluated again as a new code revision.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from eoh.eoh.eoh import EOH, _normalize_fitness

from agent_skill_loop.client import ProviderFailure, http_post_with_deadline


REPAIRABLE_ERRORS = frozenset({
    "invalid_code",
    "missing_entrypoint",
    "invalid_return",
    "candidate_exception",
    "forbidden_attribute",
    "forbidden_rebinding",
})

_NON_REPAIRABLE_ATTRIBUTES = frozenset({
    "open", "read", "write", "tofile", "fromfile", "save", "load",
    "system", "popen", "socket", "__dict__", "__class__",
})


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_repairable(diagnostic: Mapping[str, Any] | None) -> bool:
    """Apply the deterministic first-version repair allowlist."""
    if not isinstance(diagnostic, Mapping):
        return False
    code = diagnostic.get("error_code")
    if code not in REPAIRABLE_ERRORS:
        return False
    if code == "forbidden_attribute":
        detail = str(diagnostic.get("error_detail") or "").strip().lower()
        if not detail or detail in _NON_REPAIRABLE_ATTRIBUTES or detail.startswith("__"):
            return False
    return True


def _parse_repair_response(response: str) -> dict[str, str]:
    try:
        payload = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("repair_protocol_invalid_json") from None
    if not isinstance(payload, dict) or set(payload) != {"algorithm", "code", "repair_summary"}:
        raise ValueError("repair_protocol_invalid_keys")
    if any(not isinstance(payload[key], str) or not payload[key].strip() for key in payload):
        raise ValueError("repair_protocol_invalid_fields")
    return {key: payload[key] for key in ("algorithm", "code", "repair_summary")}


def build_repair_prompt(
    *,
    task_description: str,
    template_program: str,
    problem_contract: Mapping[str, Any],
    operator: str,
    candidate_id: str,
    original_code: str,
    original_code_sha256: str,
    diagnostic: Mapping[str, Any],
    allowed_capabilities: Mapping[str, Any],
) -> str:
    """Render the only information the repair model is allowed to use."""
    payload = {
        "role": "execute_repair",
        "kind": "bounded_code_repair",
        "instruction": (
            "Repair only the execution/evaluation failure in this generated candidate. "
            "Preserve the algorithmic idea where possible. Return exactly one JSON object "
            "with the keys algorithm, code, repair_summary. Do not return objective, valid, "
            "budget, acceptance, or stop decisions. The code must be complete and executable."
        ),
        "task_description": task_description,
        "problem_contract": dict(problem_contract),
        "candidate": {
            "candidate_id": candidate_id,
            "operator": operator,
            "revision": "original",
            "code_sha256": original_code_sha256,
            "code": original_code,
        },
        "diagnostic": {
            "stage": diagnostic.get("stage", "execution"),
            "error_code": diagnostic.get("error_code"),
            "error_detail": diagnostic.get("error_detail"),
            "line": diagnostic.get("line"),
            "column": diagnostic.get("column"),
        },
        "allowed_capabilities": {
            **dict(allowed_capabilities),
            "instruction": (
                "Use only these evaluator-approved capabilities. Do not add filesystem, network, "
                "subprocess, reflection, or unsafe operations."
            ),
        },
        "interface_template": template_program,
        "output_schema": {
            "algorithm": "short description consistent with the repaired code",
            "code": "full repaired Python source",
            "repair_summary": "short description of the repair",
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class LocalRepairRequester:
    """One-shot worker-side caller to the parent process's request gateway."""

    def __init__(self, endpoint: str, *, deadline: float, timeout: float) -> None:
        self.endpoint = endpoint
        self.deadline = deadline
        self.timeout = timeout
        self.last_request_index: int | None = None

    def __call__(self, prompt: str, *, purpose: str = "eoh_repair", problem: str = "", timeout: float | None = None) -> str:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderFailure("wall_time_exhausted", retryable=False)
        request_timeout = min(float(timeout or self.timeout), remaining)
        body = json.dumps({"prompt": prompt, "purpose": purpose}, ensure_ascii=False).encode("utf-8")
        status, raw = http_post_with_deadline(
            self.endpoint,
            {"Content-Type": "application/json", "User-Agent": "eoh-bounded-repair/0908"},
            body,
            request_timeout,
        )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderFailure("repair_provider_protocol_error", status, retryable=False) from None
        if status != 200:
            error_code = str(payload.get("error_code") or payload.get("error") or "repair_provider_failed")
            raise ProviderFailure(error_code, status, retryable=False)
        content = payload.get("content")
        if not isinstance(content, list) or not content or not isinstance(content[0], str) or not content[0].strip():
            raise ProviderFailure("repair_empty_completion", status, retryable=False)
        request_index = payload.get("request_index")
        self.last_request_index = request_index if isinstance(request_index, int) else None
        return content[0]


class RepairingEOH(EOH):
    """Pinned EOH with a single, deterministic repair opportunity per offspring."""

    def __init__(
        self,
        config: Any,
        problem: Any,
        *,
        repair_request: Callable[..., str],
        max_repairs_per_candidate: int = 1,
        max_repair_requests_total: int | None = None,
    ) -> None:
        super().__init__(config, problem)
        if max_repairs_per_candidate not in {0, 1}:
            raise ValueError("max_repairs_per_candidate_invalid")
        if max_repair_requests_total is not None and max_repair_requests_total < 0:
            raise ValueError("max_repair_requests_total_invalid")
        self.repair_request = repair_request
        self.max_repairs_per_candidate = int(max_repairs_per_candidate)
        self.max_repair_requests_total = max_repair_requests_total
        self._repair_lock = threading.Lock()
        self._repair_candidate_seq = 0
        self.repair_triggered = 0
        self.repair_attempted = 0
        self.repair_succeeded = 0
        self.repair_failed = 0
        self.repair_skipped = 0

    @property
    def _repair_log(self) -> Path:
        return Path(self.output_path) / "results" / "repair_events.jsonl"

    def _next_candidate_id(self) -> str:
        with self._repair_lock:
            self._repair_candidate_seq += 1
            return f"candidate_{self._repair_candidate_seq}"

    def _append_repair_event(self, payload: Mapping[str, Any]) -> None:
        path = self._repair_log
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._repair_lock:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(payload), ensure_ascii=False, allow_nan=False) + "\n")

    def _diagnose(self, code: str) -> dict[str, Any] | None:
        method = getattr(self.problem, "latest_evaluation_for_code", None)
        if not callable(method):
            return None
        row = method(code)
        if not isinstance(row, Mapping):
            return None
        evaluation = row.get("evaluation")
        result = dict(row)
        if isinstance(evaluation, Mapping):
            result.update(evaluation)
        return result

    def _repair_one(
        self,
        *,
        offspring: dict[str, Any],
        operator: str,
        candidate_id: str,
        diagnostic: Mapping[str, Any],
    ) -> dict[str, Any]:
        original_code = str(offspring.get("code") or "")
        original_hash = _sha256(original_code)
        if not is_repairable(diagnostic):
            self.repair_skipped += 1
            self._append_repair_event({
                "state": "skipped", "reason": "error_not_allowlisted", "candidate_id": candidate_id,
                "operator": operator, "original_code_sha256": original_hash, "diagnostic": dict(diagnostic),
            })
            return offspring
        with self._repair_lock:
            self.repair_triggered += 1
            if not (
                self.max_repairs_per_candidate > 0
                and (self.max_repair_requests_total is None or self.repair_attempted < self.max_repair_requests_total)
            ):
                self.repair_skipped += 1
                reason = "repair_limit" if self.max_repairs_per_candidate <= 0 else "repair_request_limit"
                skip = True
            else:
                self.repair_attempted += 1
                reason = None
                skip = False
        if skip:
            self._append_repair_event({
                "state": "skipped", "reason": reason, "candidate_id": candidate_id,
                "operator": operator, "original_code_sha256": original_hash, "diagnostic": dict(diagnostic),
            })
            return offspring

        prompt = build_repair_prompt(
            task_description=self.problem.task_description,
            template_program=self.problem.template_program,
            problem_contract={
                "problem": self.problem.spec.problem_id,
                "entrypoint": self.problem.spec.entrypoint,
                "interface_version": self.problem.spec.interface_version,
                "suite_hash": self.problem.suite.get("content_hash"),
            },
            operator=operator,
            candidate_id=candidate_id,
            original_code=original_code,
            original_code_sha256=original_hash,
            diagnostic=diagnostic,
            allowed_capabilities={
                "imports": sorted(self.problem.spec.allowed_import_roots),
                "numpy_math_roots": sorted(self.problem.spec.np_math_roots),
                "numpy_attributes": sorted(self.problem.spec.numpy_attributes),
                "math_attributes": sorted(self.problem.spec.math_attributes),
                "safe_builtins": sorted(self.problem.spec.safe_builtins),
            },
        )
        event_base = {
            "candidate_id": candidate_id,
            "operator": operator,
            "original_code_sha256": original_hash,
            "diagnostic": dict(diagnostic),
            "generation_request_ref": (
                f"results/exchanges/request_{diagnostic.get('source_request_index')}.json"
                if isinstance(diagnostic.get("source_request_index"), int) else None
            ),
            "repair_prompt_sha256": _sha256(prompt),
        }
        self._append_repair_event({**event_base, "state": "request_started"})
        try:
            # Repair is an LLM request, not solver execution.  Do not pass the
            # candidate evaluator's short timeout here; the requester owns the
            # model timeout and still clamps it to the global wall deadline.
            response = self.repair_request(prompt, purpose="eoh_repair", problem=self.problem.spec.problem_id)
            repaired = _parse_repair_response(response)
        except Exception as exc:
            self.repair_failed += 1
            self._append_repair_event({**event_base, "state": "request_failed", "error_code": getattr(exc, "error_code", type(exc).__name__)})
            return offspring
        repaired_code = repaired["code"]
        repaired_hash = _sha256(repaired_code)
        if repaired_hash == original_hash:
            self.repair_failed += 1
            self._append_repair_event({**event_base, "state": "failed", "reason": "repair_did_not_change_code", "evaluated_code_sha256": repaired_hash})
            return offspring

        repair_index = getattr(self.repair_request, "last_request_index", None)
        context = {
            "origin": "generated_repair",
            "candidate_id": candidate_id,
            "revision": "repair_1",
            "original_code_sha256": original_hash,
            "generation_request_ref": event_base["generation_request_ref"],
            "repair_request_ref": f"results/exchanges/request_{repair_index}.json" if isinstance(repair_index, int) else None,
            "repair_prompt_sha256": event_base["repair_prompt_sha256"],
        }
        setter = getattr(self.problem, "set_evaluation_context", None)
        if callable(setter):
            setter(context)
        try:
            fitness = self._eval_executor.submit(
                _eval_with_timeout, self.problem, repaired_code, self.problem.timeout
            ).result()
        except Exception:
            fitness = None
        finally:
            if callable(setter):
                setter(None)
        repair_eval = self._diagnose(repaired_code) or {}
        repaired_objective = _normalize_fitness(fitness)
        valid = repaired_objective is not None and bool(repair_eval.get("evaluation", {}).get("valid", True))
        result = {
            **event_base,
            "state": "succeeded" if valid else "failed",
            "revision": "repair_1",
            "evaluated_code_sha256": repaired_hash,
            "repair_request_ref": context["repair_request_ref"],
            "repair_summary": repaired["repair_summary"],
            "repair_evaluation_id": repair_eval.get("evaluation_id"),
            "evaluation": repair_eval.get("evaluation"),
        }
        self._append_repair_event(result)
        if not valid:
            self.repair_failed += 1
            offspring.update({
                "algorithm": repaired["algorithm"], "code": repaired_code, "objective": None,
                "candidate_id": candidate_id, "revision": "repair_1",
                "original_code_sha256": original_hash,
            })
            return offspring
        self.repair_succeeded += 1
        offspring.update({
            "algorithm": repaired["algorithm"], "code": repaired_code,
            "objective": repaired_objective, "candidate_id": candidate_id,
            "revision": "repair_1", "original_code_sha256": original_hash,
            "repair_request_ref": context["repair_request_ref"],
        })
        return offspring

    def _build_offspring(self, population_snapshot, operator):
        offspring = super()._build_offspring(population_snapshot, operator)
        if not isinstance(offspring, dict) or not offspring.get("code"):
            return offspring
        candidate_id = self._next_candidate_id()
        if offspring.get("objective") is not None:
            return offspring
        diagnostic = self._diagnose(str(offspring["code"]))
        if diagnostic is None:
            self.repair_skipped += 1
            self._append_repair_event({
                "state": "skipped", "reason": "diagnostic_missing", "candidate_id": candidate_id,
                "operator": operator, "original_code_sha256": _sha256(str(offspring["code"])),
            })
            return offspring
        return self._repair_one(
            offspring=offspring, operator=operator, candidate_id=candidate_id, diagnostic=diagnostic
        )

    def repair_summary(self) -> dict[str, Any]:
        return {
            "mode": "bounded",
            "max_repairs_per_candidate": self.max_repairs_per_candidate,
            "max_repair_requests_total": self.max_repair_requests_total,
            "repairable_errors": sorted(REPAIRABLE_ERRORS),
            "triggered": self.repair_triggered,
            "attempted": self.repair_attempted,
            "succeeded": self.repair_succeeded,
            "failed": self.repair_failed,
            "skipped": self.repair_skipped,
        }


# Imported lazily by the worker to keep the disabled path's imports identical.
from eoh.eoh.evolution import _eval_with_timeout  # noqa: E402
