"""Immutable v1.1 benchmark, identity, and population contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


ALLOWED_REFERENCE_KINDS = frozenset({
    "known_optimum",
    "best_known",
    "solver_reference",
    "analytical_reference",
    "upstream_compatibility_reference",
})
ALLOWED_ASSET_STATUSES = frozenset({
    "original_verified",
    "regenerated_protocol_compatible",
    "missing",
})
ALLOWED_FROZEN_SELECTION_KINDS = frozenset({
    "incumbent_top1",
    "archive_topk",
    "final_population_set",
})


def _plain(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return _plain(value.as_dict())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite_json_value")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def _require_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name}_must_be_sha256")
    return value


@dataclass(frozen=True)
class MetricSpec:
    """Canonical fitness definition shared by search, selection, and reports."""

    metric_id: str
    version: str
    direction: str = "minimize"
    aggregation: str = "mean_instance_relative_gap"
    reference_kind: str = "upstream_compatibility_reference"
    reference_manifest_hash: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metric_id.strip() or not self.version.strip():
            raise ValueError("metric_identity_required")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("invalid_metric_direction")
        if self.reference_kind not in ALLOWED_REFERENCE_KINDS:
            raise ValueError("invalid_reference_kind")
        if self.reference_manifest_hash is not None:
            _require_hash(self.reference_manifest_hash, "reference_manifest_hash")

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "version": self.version,
            "direction": self.direction,
            "aggregation": self.aggregation,
            "reference_kind": self.reference_kind,
            "reference_manifest_hash": self.reference_manifest_hash,
            "config": _plain(self.config),
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())

    def score(self, raw_objective: float, reference_objective: float) -> float:
        """Return a finite relative gap; lower is better for benchmark runs."""
        if not math.isfinite(float(raw_objective)) or not math.isfinite(float(reference_objective)):
            raise ValueError("nonfinite_metric_input")
        if reference_objective <= 0:
            raise ValueError("nonpositive_reference_objective")
        if self.direction != "minimize":
            raise ValueError("relative_gap_requires_minimize")
        return (float(raw_objective) - float(reference_objective)) / float(reference_objective)

    def aggregate(self, instance_scores: Sequence[float]) -> float:
        if not instance_scores or any(not math.isfinite(float(item)) for item in instance_scores):
            raise ValueError("invalid_metric_scores")
        return float(sum(float(item) for item in instance_scores) / len(instance_scores))


@dataclass(frozen=True)
class BenchmarkSpec:
    """A benchmark profile with explicit train/test and provenance identities."""

    benchmark_id: str
    profile: str
    problem_id: str
    upstream_repo: str
    upstream_commit: str
    train_manifest_hash: str
    test_manifest_hash: str
    reference_manifest_hash: str
    metric_spec_hash: str
    asset_status: str = "regenerated_protocol_compatible"
    upstream_code_profile: str = "upstream_code"
    paper_protocol_profile: str = "paper_protocol"
    deviations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("train_manifest_hash", "test_manifest_hash", "reference_manifest_hash", "metric_spec_hash"):
            _require_hash(getattr(self, name), name)
        if self.asset_status not in ALLOWED_ASSET_STATUSES:
            raise ValueError("invalid_benchmark_asset_status")

    def as_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "profile": self.profile,
            "problem_id": self.problem_id,
            "upstream_repo": self.upstream_repo,
            "upstream_commit": self.upstream_commit,
            "train_manifest_hash": self.train_manifest_hash,
            "test_manifest_hash": self.test_manifest_hash,
            "reference_manifest_hash": self.reference_manifest_hash,
            "metric_spec_hash": self.metric_spec_hash,
            "asset_status": self.asset_status,
            "profiles": {
                "upstream_code": self.upstream_code_profile,
                "paper_protocol": self.paper_protocol_profile,
            },
            "deviations": list(self.deviations),
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())


def evaluation_identity(
    *,
    candidate_code_sha256: str,
    problem_spec_hash: str,
    data_manifest_hash: str,
    evaluator_hash: str,
    metric_spec_hash: str,
) -> str:
    """Hash the complete evaluation identity, never just a code hash."""
    fields = {
        "candidate_code_sha256": _require_hash(candidate_code_sha256, "candidate_code_sha256"),
        "problem_spec_hash": _require_hash(problem_spec_hash, "problem_spec_hash"),
        "data_manifest_hash": _require_hash(data_manifest_hash, "data_manifest_hash"),
        "evaluator_hash": _require_hash(evaluator_hash, "evaluator_hash"),
        "metric_spec_hash": _require_hash(metric_spec_hash, "metric_spec_hash"),
    }
    return sha256_json(fields)


def _population_member(member: Mapping[str, Any], index: int, metric_spec_hash: str) -> dict[str, Any]:
    if not isinstance(member, Mapping):
        raise ValueError("population_member_must_be_object")
    code = member.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("population_member_code_required")
    computed_code_hash = sha256_text(code)
    code_hash = member.get("code_sha256") or computed_code_hash
    text_hash = member.get("algorithm_text_sha256")
    algorithm = str(member.get("algorithm") or "")
    if text_hash is None:
        text_hash = sha256_text(algorithm)
    _require_hash(str(code_hash), "code_sha256")
    _require_hash(str(text_hash), "algorithm_text_sha256")
    if str(code_hash) != computed_code_hash:
        raise ValueError("population_code_hash_mismatch")
    if str(text_hash) != sha256_text(algorithm):
        raise ValueError("population_algorithm_hash_mismatch")
    objective = member.get("objective")
    if objective is not None and (isinstance(objective, bool) or not math.isfinite(float(objective))):
        raise ValueError("population_objective_invalid")
    result = {
        "generation": int(member.get("generation", 0)),
        "member_index": int(member.get("member_index", index)),
        "algorithm": algorithm,
        "algorithm_text_sha256": str(text_hash),
        "code": code,
        "code_sha256": str(code_hash),
        "objective": None if objective is None else float(objective),
        "evaluation_id": member.get("evaluation_id"),
        "revision": str(member.get("revision") or "original"),
        "origin": str(member.get("origin") or "official_eoh"),
        "metric_spec_hash": str(member.get("metric_spec_hash") or metric_spec_hash),
    }
    if result["metric_spec_hash"] != metric_spec_hash:
        raise ValueError("population_metric_spec_mismatch")
    return result


@dataclass(frozen=True)
class PopulationSnapshot:
    """Faithful ordered snapshot of the official final population."""

    generation: int
    members: tuple[Mapping[str, Any], ...]
    metric_spec_hash: str
    problem_spec_hash: str | None = None
    data_manifest_hash: str | None = None
    evaluator_hash: str | None = None
    origin: str = "official_eoh_final_population"

    def __post_init__(self) -> None:
        _require_hash(self.metric_spec_hash, "metric_spec_hash")
        for name in ("problem_spec_hash", "data_manifest_hash", "evaluator_hash"):
            value = getattr(self, name)
            if value is not None:
                _require_hash(value, name)

    @classmethod
    def from_members(
        cls,
        members: Sequence[Mapping[str, Any]],
        *,
        generation: int,
        metric_spec_hash: str,
        problem_spec_hash: str | None = None,
        data_manifest_hash: str | None = None,
        evaluator_hash: str | None = None,
        origin: str = "official_eoh_final_population",
    ) -> "PopulationSnapshot":
        _require_hash(metric_spec_hash, "metric_spec_hash")
        # Do not sort, deduplicate, or truncate here.  member_index and list
        # order are evidence about what the official engine returned.
        normalized = tuple(_population_member(item, index, metric_spec_hash) for index, item in enumerate(members))
        return cls(generation=int(generation), members=normalized, metric_spec_hash=metric_spec_hash,
                   problem_spec_hash=problem_spec_hash, data_manifest_hash=data_manifest_hash,
                   evaluator_hash=evaluator_hash, origin=origin)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PopulationSnapshot":
        if not isinstance(payload, Mapping) or not isinstance(payload.get("members"), list):
            raise ValueError("population_snapshot_invalid")
        snapshot = cls.from_members(
            payload["members"],
            generation=int(payload.get("generation", 0)),
            metric_spec_hash=str(payload.get("metric_spec_hash")),
            problem_spec_hash=payload.get("problem_spec_hash"),
            data_manifest_hash=payload.get("data_manifest_hash"),
            evaluator_hash=payload.get("evaluator_hash"),
            origin=str(payload.get("origin") or "official_eoh_final_population"),
        )
        expected = payload.get("content_hash")
        if expected is not None and expected != snapshot.content_hash:
            raise ValueError("population_snapshot_hash_mismatch")
        return snapshot

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "algorithm-optimization-population-snapshot/v1",
            "generation": self.generation,
            "metric_spec_hash": self.metric_spec_hash,
            "problem_spec_hash": self.problem_spec_hash,
            "data_manifest_hash": self.data_manifest_hash,
            "evaluator_hash": self.evaluator_hash,
            "origin": self.origin,
            "members": [_plain(item) for item in self.members],
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())


@dataclass(frozen=True)
class SeedSelection:
    """Deterministic derivation from a population snapshot."""

    source_snapshot_hash: str
    target_population_size: int
    candidates_considered: int
    valid_members: int
    selected_members: tuple[Mapping[str, Any], ...]
    metric_spec_hash: str
    terminated: bool = False
    termination_reason: str | None = None

    @classmethod
    def from_snapshot(cls, snapshot: PopulationSnapshot, target_population_size: int) -> "SeedSelection":
        if isinstance(target_population_size, bool) or target_population_size < 1:
            raise ValueError("invalid_target_population_size")
        valid = [
            (index, item) for index, item in enumerate(snapshot.members)
            if item.get("objective") is not None and isinstance(item.get("code"), str) and item.get("code_sha256")
        ]
        # The first official member owns a duplicate code.  This preserves
        # provenance before the stable fitness ordering is applied.
        unique: dict[str, tuple[int, Mapping[str, Any]]] = {}
        for index, item in valid:
            unique.setdefault(str(item["code_sha256"]), (index, item))
        ordered = sorted(unique.values(), key=lambda pair: (float(pair[1]["objective"]), pair[0]))
        selected = tuple(item for _index, item in ordered[:target_population_size])
        terminated = len(selected) < target_population_size
        return cls(
            source_snapshot_hash=snapshot.content_hash,
            target_population_size=target_population_size,
            candidates_considered=len(snapshot.members),
            valid_members=len(unique),
            selected_members=selected,
            metric_spec_hash=snapshot.metric_spec_hash,
            terminated=terminated,
            termination_reason="insufficient_valid_seeds" if terminated else None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "algorithm-optimization-seed-selection/v1",
            "source_snapshot_hash": self.source_snapshot_hash,
            "target_population_size": self.target_population_size,
            "candidates_considered": self.candidates_considered,
            "valid_members": self.valid_members,
            "selected_members": [_plain(item) for item in self.selected_members],
            "metric_spec_hash": self.metric_spec_hash,
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())


@dataclass(frozen=True)
class FrozenSelection:
    selection_kind: str
    members: tuple[Mapping[str, Any], ...]
    training_metric_spec_hash: str
    source_ref: str | None = None
    k_requested: int | None = None
    locked: bool = True
    test_evaluated: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FrozenSelection":
        if not isinstance(payload, Mapping) or not isinstance(payload.get("members"), list):
            raise ValueError("frozen_selection_invalid")
        values = dict(payload)
        declared_hash = values.pop("content_hash", None)
        values.pop("schema_version", None)
        try:
            selection = cls(
                selection_kind=str(values["selection_kind"]),
                members=tuple(values["members"]),
                training_metric_spec_hash=str(values["training_metric_spec_hash"]),
                source_ref=values.get("source_ref"),
                k_requested=values.get("k_requested"),
                locked=values.get("locked", True),
                test_evaluated=values.get("test_evaluated", False),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"frozen_selection_invalid:{exc}") from exc
        if declared_hash is not None and declared_hash != selection.content_hash:
            raise ValueError("frozen_selection_hash_mismatch")
        return selection

    def __post_init__(self) -> None:
        if self.selection_kind not in ALLOWED_FROZEN_SELECTION_KINDS:
            raise ValueError("invalid_selection_kind")
        _require_hash(self.training_metric_spec_hash, "training_metric_spec_hash")
        if self.k_requested is not None and (
            isinstance(self.k_requested, bool)
            or not isinstance(self.k_requested, int)
            or self.k_requested < 1
        ):
            raise ValueError("invalid_selection_k")
        if not isinstance(self.locked, bool) or not isinstance(self.test_evaluated, bool):
            raise ValueError("frozen_selection_flags_invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "algorithm-optimization-frozen-selection/v1",
            "selection_kind": self.selection_kind,
            "members": [_plain(item) for item in self.members],
            "training_metric_spec_hash": self.training_metric_spec_hash,
            "source_ref": self.source_ref,
            "k_requested": self.k_requested,
            "locked": self.locked,
            "test_evaluated": self.test_evaluated,
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())


@dataclass(frozen=True)
class ExperimentManifest:
    """Hashable run manifest that prevents cross-experiment result mixing."""

    benchmark_spec_hash: str
    metric_spec_hash: str
    eoh_commit: str
    runtime_hash: str
    skill_hash: str
    model: str
    endpoint_identity: str
    inheritance_mode: str
    feedback_mode: str
    agent_guidance: bool
    repair_mode: str
    memory_enabled: bool
    evaluation_budget: int
    population_size: int
    rounds: int
    round_budget: int
    search_seed: int
    manifest_version: str = "v1"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("benchmark_spec_hash", "metric_spec_hash", "runtime_hash", "skill_hash"):
            _require_hash(getattr(self, name), name)
        for name in ("eoh_commit", "model", "endpoint_identity", "inheritance_mode", "feedback_mode", "repair_mode"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name}_required")
        for name in ("agent_guidance", "memory_enabled"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name}_must_be_bool")
        for name in ("evaluation_budget", "population_size", "rounds", "round_budget", "search_seed"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name}_must_be_integer")
        if self.evaluation_budget < 0 or self.population_size < 1 or self.rounds < 1 or self.round_budget < 1:
            raise ValueError("invalid_experiment_budget")
        if self.inheritance_mode not in {"incumbent_only", "population_seeds", "explicit_seeds"}:
            raise ValueError("invalid_inheritance_mode")
        if self.feedback_mode not in {"off", "runtime_facts"}:
            raise ValueError("invalid_feedback_mode")
        if self.repair_mode not in {"off", "bounded"}:
            raise ValueError("invalid_repair_mode")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "algorithm-optimization-experiment-manifest/" + self.manifest_version,
            "benchmark_spec_hash": self.benchmark_spec_hash,
            "metric_spec_hash": self.metric_spec_hash,
            "eoh_commit": self.eoh_commit,
            "runtime_hash": self.runtime_hash,
            "skill_hash": self.skill_hash,
            "model": self.model,
            "endpoint_identity": self.endpoint_identity,
            "inheritance_mode": self.inheritance_mode,
            "feedback_mode": self.feedback_mode,
            "agent_guidance": bool(self.agent_guidance),
            "repair_mode": self.repair_mode,
            "memory_enabled": bool(self.memory_enabled),
            "evaluation_budget": self.evaluation_budget,
            "population_size": self.population_size,
            "rounds": self.rounds,
            "round_budget": self.round_budget,
            "search_seed": self.search_seed,
            "extra": _plain(self.extra),
        }

    @property
    def content_hash(self) -> str:
        return sha256_json(self.as_dict())
