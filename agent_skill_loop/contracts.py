"""Frozen data contracts for the skill loop. No FME/RQ fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


PROBLEM_CVRP = "cvrp_construct"
ENTRYPOINT_CVRP = "select_next_node"
JOURNAL_SCHEMA = "agent-skill-journal/v1"
SKILL_SCHEMA = "algorithm-skill/v1"
OBJECTIVE_DIRECTION = "minimize"

# Production search identity: the pinned upstream EoH commit in pyproject.toml.
EOH_COMMIT = "472545785c936dcfc863d2bc0d6109cf23c7ce62"
OFFICIAL_SEARCH_POLICY_ID = "official_eoh"

DEFAULT_SEED = 20260908
DEFAULT_SIZE = 20
DEFAULT_COUNT = 3
DEFAULT_SPLIT = "dev_train"
DEFAULT_SOLVER_TIMEOUT = 20.0
DEFAULT_REQUEST_TIMEOUT = 90.0
DEFAULT_WALL_SECONDS = 420.0



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
    metrics: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "valid": self.valid,
            "objective": self.objective,
            "instance_objectives": list(self.instance_objectives),
            "suite_hash": self.suite_hash,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }
        if self.metrics is not None:
            payload["metrics"] = self.metrics
        return payload


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
    search_policy_id: str = "unspecified"
    search_policy_version: str = "unknown"
    search_policy_fixture_only: bool = False
    origin: str | None = None  # baseline | explicit_parent | generated | imported
    official_objective: float | None = None
    legacy_unverified: bool = False
    integration_mode: str | None = None
    repair_policy_version: str | None = None

    def metadata(self) -> dict[str, Any]:
        search_policy: dict[str, Any] = {
            "id": self.search_policy_id,
            "version": self.search_policy_version,
        }
        if self.search_policy_fixture_only:
            search_policy["fixture_only"] = True
        if self.integration_mode is not None:
            search_policy["integration_mode"] = self.integration_mode
        if self.repair_policy_version is not None:
            search_policy["repair_policy_version"] = self.repair_policy_version
        payload = {
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
            "search_policy": search_policy,
        }
        if self.origin is not None:
            payload["origin"] = self.origin
        if self.official_objective is not None:
            payload["official_objective"] = self.official_objective
        if self.legacy_unverified:
            payload["legacy_unverified"] = True
        return payload
