"""Problem contracts. First version ships CVRP only."""

from agent_skill_loop.problems.cvrp import (
    BASELINE_CODE,
    ENTRYPOINT,
    PROBLEM_NAME,
    TASK_DESCRIPTION,
    TEMPLATE_PROGRAM,
    build_suite,
)

__all__ = [
    "BASELINE_CODE",
    "ENTRYPOINT",
    "PROBLEM_NAME",
    "TASK_DESCRIPTION",
    "TEMPLATE_PROGRAM",
    "build_suite",
]
