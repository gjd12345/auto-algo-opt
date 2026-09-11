"""Official EoH BaseProblem that scores on the frozen three-instance suite.

Does not change EoH operators or prompts. Fitness is the same mean travel
distance used by agent_skill_loop (lower is better).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eoh import BaseProblem

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SOLVER_TIMEOUT, DEFAULT_SPLIT, EvaluationResult
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.problems.cvrp import TASK_DESCRIPTION, TEMPLATE_PROGRAM, build_suite


class FrozenCVRPConstruct(BaseProblem):
    template_program = TEMPLATE_PROGRAM
    task_description = TASK_DESCRIPTION

    def __init__(
        self,
        suite: dict[str, Any] | None = None,
        *,
        timeout: int = int(DEFAULT_SOLVER_TIMEOUT),
        n_processes: int = 1,
        seed: int = DEFAULT_SEED,
        size: int = DEFAULT_SIZE,
        count: int = DEFAULT_COUNT,
        split: str = DEFAULT_SPLIT,
        fail_log: str | Path | None = None,
    ) -> None:
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.suite = suite or build_suite(seed, split=split, count=count, size=size)
        self.fail_log = str(fail_log) if fail_log is not None else None

    def evaluate(self, code_string: str) -> float | None:
        # The inner worker carries a parent-pid watchdog (eval_worker.py) so it
        # exits when this wrapper process is killed by the official outer
        # timeout. The 1s margin below the outer solver timeout is defense in
        # depth, not the primary cancellation mechanism.
        result = SubprocessEvaluator(timeout=max(0.5, float(self.timeout) - 1.0)).evaluate(code_string, self.suite)
        if not result.valid or result.objective is None:
            self._record_failure(code_string, result)
            return None
        return float(result.objective)

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
