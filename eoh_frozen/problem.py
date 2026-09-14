"""Official EoH BaseProblem adapter for a registered frozen problem suite.

Does not change EoH operators or prompts. Fitness is supplied by the selected
problem contract and is always evaluated in the isolated kernel worker.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from eoh import BaseProblem

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SOLVER_TIMEOUT, DEFAULT_SPLIT, EvaluationResult
from agent_skill_loop.session_contracts import MAX_ROUND_CONTEXT_CHARS
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.problems.base import ProblemSpec


class FrozenProblem(BaseProblem):
    """Official EoH adapter for any registered ProblemSpec.

    The original adapter hard-coded CVRP, which made the official entrypoint
    unsafe to reuse for the TSP contracts: it evaluated one problem and then
    labelled the exported asset as another.  This adapter binds the problem
    identity once and carries it through evaluation and evidence logging.
    """

    def __init__(
        self,
        suite: dict[str, Any] | None = None,
        *,
        spec: ProblemSpec,
        timeout: int = int(DEFAULT_SOLVER_TIMEOUT),
        n_processes: int = 1,
        seed: int = DEFAULT_SEED,
        size: int = DEFAULT_SIZE,
        count: int = DEFAULT_COUNT,
        split: str = DEFAULT_SPLIT,
        fail_log: str | Path | None = None,
        evaluation_log: str | Path | None = None,
        deadline: float | None = None,
        origin: str = "unknown",
        round_context: str | None = None,
        session: dict | None = None,
        metric_spec_hash: str | None = None,
        data_manifest_hash: str | None = None,
        problem_spec_hash: str | None = None,
        seed_bindings: Mapping[str, Mapping[str, Any]] | None = None,
        # Kept as a source-compatible no-op for older callers.  A count alone
        # cannot identify a spawned child evaluation and must never be used to
        # infer provenance; callers must provide exact code-hash bindings.
        seed_evaluations: int = 0,
    ) -> None:
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.spec = spec
        self.session = session
        self.metric_spec_hash = metric_spec_hash
        self.data_manifest_hash = data_manifest_hash
        self.problem_spec_hash = problem_spec_hash
        self._seed_bindings_by_code: dict[str, dict[str, Any]] = {}
        if seed_bindings is not None:
            if not isinstance(seed_bindings, Mapping):
                raise ValueError("seed_bindings_invalid")
            for code_hash, context in seed_bindings.items():
                if (not isinstance(code_hash, str) or len(code_hash) != 64
                        or any(char not in "0123456789abcdef" for char in code_hash)
                        or not isinstance(context, Mapping)):
                    raise ValueError("seed_bindings_invalid")
                normalized = dict(context)
                if (normalized.get("origin") != "population_seed"
                        or not isinstance(normalized.get("candidate_id"), str)
                        or not normalized["candidate_id"]
                        or normalized.get("revision") != "original"):
                    raise ValueError("seed_binding_context_invalid")
                self._seed_bindings_by_code[code_hash] = normalized
        self.suite = suite or spec.build_suite(seed, split=split, count=count, size=size)
        if self.suite.get("problem") != spec.problem_id:
            raise ValueError("suite_problem_mismatch")
        self.deadline = deadline
        self.origin = origin
        if round_context is not None and len(round_context) > MAX_ROUND_CONTEXT_CHARS:
            raise ValueError("plan_context_too_large")
        self.round_context = round_context.strip() if isinstance(round_context, str) and round_context.strip() else None
        self.owner_pid = os.getpid()
        self.fail_log = str(fail_log) if fail_log is not None else None
        self.evaluation_log = str(evaluation_log) if evaluation_log is not None else None
        self.evaluation_context: dict[str, Any] | None = None
        self._log_lock = threading.Lock()

    def __getstate__(self) -> dict[str, Any]:
        """Keep the problem picklable for EoH's spawn-based eval workers."""
        state = self.__dict__.copy()
        state.pop("_log_lock", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._log_lock = threading.Lock()

    @property
    def template_program(self) -> str:
        return self.spec.template_program

    @property
    def task_description(self) -> str:
        # Generation and bounded repair receive the same allowlist from the
        # immutable ProblemSpec.  The round context remains a separate,
        # advisory input and may refine the search without changing safety or
        # evaluation authority.
        description = self.spec.task_description + "\n\n" + self.spec.capability_contract_text()
        if self.round_context is not None:
            description += "\n\n" + self.round_context
        return description

    def evaluate(self, code_string: str) -> float | None:
        result = self.evaluate_result(code_string)
        if not result.valid or result.objective is None:
            return None
        return float(result.objective)

    def evaluate_result(self, code_string: str) -> EvaluationResult:
        """Evaluate and retain the full per-instance evidence record."""
        if os.getpid() != self.owner_pid and not getattr(self, "_owner_watch_started", False):
            from agent_skill_loop.eval_worker import _watch_parent
            threading.Thread(target=_watch_parent, args=(self.owner_pid,), daemon=True).start()
            self._owner_watch_started = True
        # The inner worker carries a parent-pid watchdog (eval_worker.py) so it
        # exits when this wrapper process is killed by the official outer
        # timeout. The 1s margin below the outer solver timeout is defense in
        # depth, not the primary cancellation mechanism.
        timeout = max(0.05, float(self.timeout) - 1.0)
        if self.deadline is not None:
            timeout = min(timeout, self.deadline - time.monotonic())
        if timeout <= 0:
            return EvaluationResult(False, None, (), self.suite.get("content_hash"), "wall_time_limit", 0)
        evaluation_id = (self.evaluation_context or {}).get("evaluation_id") or uuid.uuid4().hex
        self._record_evaluation(code_string, None, evaluation_id=evaluation_id)
        result = SubprocessEvaluator(timeout=timeout).evaluate(code_string, self.suite)
        self._record_evaluation(code_string, result, evaluation_id=evaluation_id)
        if not result.valid or result.objective is None:
            self._record_failure(code_string, result)
        return result

    def set_evaluation_context(self, context: dict[str, Any] | None) -> None:
        """Attach explicit candidate-revision provenance to the next evaluation."""
        self.evaluation_context = dict(context) if context is not None else None

    def clear_seed_bindings(self) -> None:
        """Stop treating matching code as a seed after official init ends."""
        self._seed_bindings_by_code.clear()

    def _context_for_code(self, code: str) -> dict[str, Any]:
        explicit = dict(self.evaluation_context or {})
        if explicit:
            return explicit
        code_hash = hashlib.sha256(str(code).encode("utf-8")).hexdigest()
        return dict(self._seed_bindings_by_code.get(code_hash) or {})

    def latest_evaluation_for_code(self, code: str) -> dict[str, Any] | None:
        """Return the latest durable evaluation row for an exact code hash."""
        if not self.evaluation_log:
            return None
        code_hash = hashlib.sha256(str(code).encode("utf-8")).hexdigest()
        path = Path(self.evaluation_log)
        if not path.is_file():
            return None
        found = None
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("code_sha256") == code_hash and row.get("evaluation") is not None:
                found = {**row, "evaluation_line": line_number}
        return found

    def evaluation_for_identity(self, code: str, context: dict[str, Any]) -> dict[str, Any] | None:
        if not self.evaluation_log or not Path(self.evaluation_log).is_file():
            return None
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        for line_number, line in enumerate(Path(self.evaluation_log).read_text(encoding="utf-8").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (all(context.get(k) is not None and row.get(k) == context[k]
                    for k in ("candidate_id", "revision", "evaluation_id"))
                    and row.get("code_sha256") == code_hash
                    and row.get("suite_hash") == self.suite["content_hash"]
                    and row.get("evaluator_hash") == evaluator_source_hash()
                    and (self.metric_spec_hash is None or row.get("metric_spec_hash") == self.metric_spec_hash)
                    and row.get("evaluation") is not None):
                return {**row, "evaluation_line": line_number}
        return None

    def _record_evaluation(self, code: str, result: EvaluationResult | None, *, evaluation_id: str) -> None:
        if not self.evaluation_log:
            return
        payload = {
            "code": code,
            "code_sha256": hashlib.sha256(str(code).encode("utf-8")).hexdigest(),
            "problem": self.spec.problem_id,
            "entrypoint": self.spec.entrypoint,
            "evaluator_hash": evaluator_source_hash(),
            "origin": self.origin,
            "pid": os.getpid(),
            "suite_hash": self.suite.get("content_hash"),
            "evaluation_id": evaluation_id,
            "metric_spec_hash": self.metric_spec_hash,
            "data_manifest_hash": self.data_manifest_hash,
            "problem_spec_hash": self.problem_spec_hash,
            "evaluation": result.as_dict() if result is not None else None,
        }
        context = self._context_for_code(code)
        if context:
            payload.update(context)
        if context.get("origin") == "generated" or (not context and self.origin == "engine"):
            latest = Path(self.evaluation_log).parent / "latest_exchange.json"
            exchange = json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
            # Production uses one sampler/evaluator, so this is the response
            # immediately preceding this evaluation. Seeds follow only probe.
            payload["origin"] = context.get("origin") or ("generated" if exchange.get("purpose") == "eoh_generation" else "explicit_parent")
            payload["source_request_index"] = exchange.get("request_index") if payload["origin"] == "generated" else None
            payload["prompt_sha256"] = exchange.get("prompt_sha256")
        if self.session and not payload.get("candidate_id"):
            payload["candidate_id"] = (f"candidate_{payload['source_request_index']}" if payload.get("source_request_index") else payload["origin"])
            payload["revision"] = "original"
        if result is None:
            if self.session:
                from agent_skill_loop.session_ledger import solver_event
                solver_event(self.session, payload)
            from agent_skill_loop.skill_store import _atomic_write_text
            payload["state"] = "started"
            _atomic_write_text(Path(self.evaluation_log).parent / "evaluation_starts" / f"{evaluation_id}.json",
                               json.dumps(payload, ensure_ascii=False, allow_nan=False))
            return
        try:
            path = Path(self.evaluation_log)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_lock:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            if self.session:
                from agent_skill_loop.session_ledger import solver_event
                solver_event(self.session, payload)
        except OSError:
            # Missing evidence must not yield a usable scalar fitness.
            raise

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        return self.evaluate(program_str)

    def _record_failure(self, code: str, result: EvaluationResult) -> None:
        if not self.fail_log:
            return
        payload = {
            "error_code": result.error_code,
            "error_detail": result.error_detail,
            "elapsed_seconds": result.elapsed_seconds,
            "code": code if isinstance(code, str) else None,
        }
        try:
            path = Path(self.fail_log)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            return
