"""Official EoH BaseProblem that scores on the frozen three-instance suite.

Does not change EoH operators or prompts. Fitness is the same mean travel
distance used by agent_skill_loop (lower is better).
"""

from __future__ import annotations

from typing import Any

from eoh import BaseProblem

from agent_skill_loop.contracts import DEFAULT_COUNT, DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_SOLVER_TIMEOUT, DEFAULT_SPLIT
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
    ) -> None:
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.suite = suite or build_suite(seed, split=split, count=count, size=size)

    def evaluate(self, code_string: str) -> float | None:
        result = SubprocessEvaluator(timeout=float(self.timeout)).evaluate(code_string, self.suite)
        if not result.valid or result.objective is None:
            return None
        return float(result.objective)

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        return self.evaluate(program_str)
