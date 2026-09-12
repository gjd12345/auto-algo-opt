"""Data contracts belonging only to the archived test harness."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
from agent_skill_loop.contracts import EvaluationResult
DEFAULT_CANDIDATE_ATTEMPTS = 3
DEFAULT_MAX_LLM_REQUESTS = 3
STAGNATION_E1_STREAK = 2

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


def better_objective(candidate: float | None, incumbent: float | None) -> bool:
    if candidate is None:
        return False
    if incumbent is None:
        return True
    return candidate < incumbent


def as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if value is not None else {}
