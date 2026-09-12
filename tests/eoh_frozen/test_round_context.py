from __future__ import annotations

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.problems.base import get_problem
from eoh_frozen.problem import FrozenProblem


def test_round_context_is_advisory_and_bounded():
    spec = get_problem("cvrp_construct")
    suite = spec.build_suite(20260908, count=1, size=6, split="dev_train")
    task = FrozenProblem(suite, spec=spec, round_context="ROUND CONTEXT: preserve capacity")
    assert task.task_description.endswith("ROUND CONTEXT: preserve capacity")
    with pytest.raises(ValueError, match="plan_context_too_large"):
        FrozenProblem(suite, spec=spec, round_context="x" * 12001)
