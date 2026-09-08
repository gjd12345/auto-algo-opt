"""Problem contracts. First version ships CVRP only."""

from agent_skill_loop.problems.base import PROBLEM_REGISTRY, ProblemSpec, get_problem, register_problem
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
    "PROBLEM_REGISTRY",
    "ProblemSpec",
    "TASK_DESCRIPTION",
    "TEMPLATE_PROGRAM",
    "build_suite",
    "get_problem",
    "register_problem",
]