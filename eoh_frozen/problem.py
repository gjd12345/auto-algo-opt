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
from typing import Any

from eoh import BaseProblem

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SOLVER_TIMEOUT, DEFAULT_SPLIT, EvaluationResult
from agent_skill_loop.contracts_3plus1 import MAX_ROUND_CONTEXT_CHARS
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
    ) -> None:
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.spec = spec
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
        if self.round_context is None:
            return self.spec.task_description
        return self.spec.task_description + "\n\n" + self.round_context

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
        evaluation_id = uuid.uuid4().hex
        self._record_evaluation(code_string, None, evaluation_id=evaluation_id)
        result = SubprocessEvaluator(timeout=timeout).evaluate(code_string, self.suite)
        self._record_evaluation(code_string, result, evaluation_id=evaluation_id)
        if not result.valid or result.objective is None:
            self._record_failure(code_string, result)
        return result

    def set_evaluation_context(self, context: dict[str, Any] | None) -> None:
        """Attach explicit candidate-revision provenance to the next evaluation."""
        self.evaluation_context = dict(context) if context is not None else None

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
            "evaluation": result.as_dict() if result is not None else None,
        }
        context = dict(self.evaluation_context or {})
        if context:
            payload.update(context)
        elif self.origin == "engine":
            latest = Path(self.evaluation_log).parent / "latest_exchange.json"
            exchange = json.loads(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
            # Production uses one sampler/evaluator, so this is the response
            # immediately preceding this evaluation. Seeds follow only probe.
            payload["origin"] = "generated" if exchange.get("purpose") == "eoh_generation" else "explicit_parent"
            payload["source_request_index"] = exchange.get("request_index") if payload["origin"] == "generated" else None
            payload["prompt_sha256"] = exchange.get("prompt_sha256")
        if result is None:
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


class FrozenCVRPConstruct(FrozenProblem):
    """Backward-compatible CVRP name for callers of the original adapter."""

    def __init__(self, suite: dict[str, Any] | None = None, **kwargs: Any) -> None:
        from agent_skill_loop.problems.base import get_problem
        super().__init__(suite, spec=get_problem("cvrp_construct"), **kwargs)
