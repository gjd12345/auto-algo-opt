"""ProblemSpec contract and problem registry.

A ProblemSpec fully describes one constructive-algorithm problem: its identity,
the evolved entrypoint, the prompt literals, the suite builder/validator, the
execution capability whitelist, and the per-instance objective evaluation used
by the worker. The CVRP spec encapsulates exactly the pre-refactor literals so
observable behavior (scores, error codes, prompt shapes) is preserved.

The registry is populated when :mod:`agent_skill_loop.evaluator` is imported
(which registers the CVRP spec). A deferred import at the bottom of this module
guarantees the registry is ready whenever :func:`get_problem` is used, without
forcing a particular import order on callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ProblemSpec:
    """Immutable contract describing one evolvable problem."""

    problem_id: str
    entrypoint: str
    interface_version: str
    task_description: str
    template_program: str
    baseline_code: str
    objective_direction: str
    split_offsets: Mapping[str, int]

    # suite lifecycle
    build_suite: Callable[..., Mapping[str, Any]]
    suite_hash: Callable[..., str]
    validate_suite: Callable[[Mapping[str, Any]], tuple[list[Mapping[str, Any]], str]]

    # per-instance objective evaluation used by the worker:
    # returns (objectives, metrics) where metrics may be None
    evaluate_instances: Callable[[Any, list[Mapping[str, Any]]], tuple[list[float], dict[str, Any] | None]]

    # execution capability whitelist
    safe_builtins: Mapping[str, Any]
    forbidden_names: frozenset[str]
    numpy_attributes: frozenset[str]
    math_attributes: frozenset[str]
    np_math_roots: frozenset[str]
    allowed_import_roots: frozenset[str]

    # Human-readable baseline provenance, not a search-policy instruction.
    baseline_description: str = ""

    @property
    def allowed_attributes(self) -> frozenset[str]:
        return self.numpy_attributes | self.math_attributes


PROBLEM_REGISTRY: dict[str, ProblemSpec] = {}


def register_problem(spec: ProblemSpec) -> None:
    """Register a problem spec by id (idempotent overwrite)."""
    PROBLEM_REGISTRY[spec.problem_id] = spec


def get_problem(problem_id: str) -> ProblemSpec:
    """Resolve a problem spec by id. Unknown ids raise ValueError("unsupported_problem")."""
    try:
        spec = PROBLEM_REGISTRY[problem_id]
    except (KeyError, TypeError):
        raise ValueError("unsupported_problem") from None
    return spec


def _load_registry() -> None:
    # Importing evaluator registers the CVRP spec. Deferred so this module has
    # no hard import-time dependency and callers can use any import order.
    from agent_skill_loop import evaluator  # noqa: F401


_load_registry()
