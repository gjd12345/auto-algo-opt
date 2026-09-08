"""Frozen data contracts for the skill loop. No FME/RQ fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


PROBLEM_CVRP = "cvrp_construct"
ENTRYPOINT_CVRP = "select_next_node"
JOURNAL_SCHEMA = "agent-skill-journal/v1"
SKILL_SCHEMA = "algorithm-skill/v1"
OBJECTIVE_DIRECTION = "minimize"

DEFAULT_SEED = 20260908
DEFAULT_SIZE = 20
DEFAULT_COUNT = 3
DEFAULT_SPLIT = "dev_train"
DEFAULT_CANDIDATE_ATTEMPTS = 3
DEFAULT_MAX_LLM_REQUESTS = 3
DEFAULT_SOLVER_TIMEOUT = 20.0
DEFAULT_REQUEST_TIMEOUT = 90.0
DEFAULT_WALL_SECONDS = 420.0

STAGNATION_E1_STREAK = 2


class Transport(Protocol):
    def request(
        self,
        prompt: str,
        *,
        purpose: str,
        problem: str,
        timeout: float | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class EvaluationResult:
    valid: bool
    objective: float | None
    instance_objectives: tuple[float, ...]
    suite_hash: str | None
    error_code: str | None
    elapsed_seconds: float
    error_detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "objective": self.objective,
            "instance_objectives": list(self.instance_objectives),
            "suite_hash": self.suite_hash,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }


@dataclass(frozen=True)
class SkillVersion:
    version_id: str
    problem: str
    entrypoint: str
    code: str
    code_sha256: str
    parent_version_id: str | None
    suite_hash: str
    evaluator_hash: str
    valid: bool
    mean_objective: float | None
    instance_objectives: tuple[float, ...]
    source_attempt_id: int | None
    description: str = ""
    repair_of_attempt_id: int | None = None
    search_policy_id: str = "fixed"
    search_policy_version: str = "v1"

    def metadata(self) -> dict[str, Any]:
        return {
            "schema_version": SKILL_SCHEMA,
            "version_id": self.version_id,
            "problem": self.problem,
            "entrypoint": self.entrypoint,
            "code_sha256": self.code_sha256,
            "parent_version_id": self.parent_version_id,
            "repair_of_attempt_id": self.repair_of_attempt_id,
            "suite_hash": self.suite_hash,
            "evaluator_hash": self.evaluator_hash,
            "valid": self.valid,
            "objective_direction": OBJECTIVE_DIRECTION,
            "mean_objective": self.mean_objective,
            "instance_objectives": list(self.instance_objectives),
            "source_attempt_id": self.source_attempt_id,
            "description": self.description,
            "search_policy": {"id": self.search_policy_id, "version": self.search_policy_version},
        }


@dataclass
class AttemptRecord:
    attempt_id: int
    operator: str
    parent_version_id: str | None
    failed_code_hash: str | None
    prompt_hash: str
    prompt_path: str
    code: str
    code_hash: str
    evaluation: EvaluationResult
    accepted_as_incumbent: bool
    llm_requests: int
    solver_calls: int
    raw_response: str = ""
    repair_of_attempt_id: int | None = None
    feedback_attempt_id: int | None = None
    accept_reason: str | None = None
    edit_target: str | None = None


@dataclass
class RunSummary:
    execution_mode: str
    loop_completed: bool
    status: str
    stop_reason: str
    generated_valid_candidates: int
    exported_skill_ids: list[str] = field(default_factory=list)
    feedback_consumed_count: int = 0
    candidate_attempts: int = 0
    llm_requests: int = 0
    solver_calls: int = 0
    wall_seconds: float = 0.0
    incumbent_version_id: str | None = None
    incumbent_is_generated: bool = False
    best_generated_version_id: str | None = None
    feedback_then_regenerated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "loop_completed": self.loop_completed,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "generated_valid_candidates": self.generated_valid_candidates,
            "exported_skill_ids": list(self.exported_skill_ids),
            "feedback_consumed_count": self.feedback_consumed_count,
            "feedback_then_regenerated": self.feedback_then_regenerated,
            "candidate_attempts": self.candidate_attempts,
            "llm_requests": self.llm_requests,
            "solver_calls": self.solver_calls,
            "wall_seconds": round(self.wall_seconds, 4),
            "incumbent_version_id": self.incumbent_version_id,
            "incumbent_is_generated": self.incumbent_is_generated,
            "best_generated_version_id": self.best_generated_version_id,
        }


def choose_operator(
    *,
    attempts_done: int,
    has_explicit_parent: bool,
    last_valid: bool | None,
) -> str:
    """Fixed policy: i1 cold start, e1 after success, m1 after failure."""
    if attempts_done == 0:
        return "e1" if has_explicit_parent else "i1"
    if last_valid is False:
        return "m1"
    return "e1"


def better_objective(candidate: float | None, incumbent: float | None) -> bool:
    if candidate is None:
        return False
    if incumbent is None:
        return True
    return candidate < incumbent


def as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value is not None else {}
