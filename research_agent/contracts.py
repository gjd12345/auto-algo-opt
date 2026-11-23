"""Data contracts, configuration, and append-only audit helpers for ``research_agent``."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

ALLOWED_HYPOTHESIS_STATUSES: frozenset[str] = frozenset({
    "proposed",
    "testing",
    "supported",
    "refuted",
    "abandoned",
    "superseded",
})

EVIDENCE_REQUIRED_STATUSES: frozenset[str] = frozenset({
    "supported",
    "refuted",
    "abandoned",
})


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, text)
    return sha256_text(text)


@dataclass(frozen=True)
class AgentConfig:
    """Immutable run configuration for an autonomous M3/M3.1/M3.2 research run."""

    run_id: str
    output_dir: str
    problem_family: str = "cvrp"
    arm_id: str = "arm_m3_3_full_dynamic"
    max_rounds: int = 3
    total_request_cap: int = 36
    outer_requests_per_round_cap: int = 4
    outer_reflect_cap: int = 2
    eoh_pop_size: int = 2
    eoh_n_pop: int = 2
    eoh_max_sample_nums: int = 8
    instance_time_budget_ms: float = 500.0
    allowed_templates: tuple[str, ...] = (
        "cvrp_sequential_construct",
        "cvrp_parallel_merge_static",
        "cvrp_parallel_merge_dynamic",
        "cvrp_ruin_recreate",
    )
    allowed_postprocess_modes: tuple[str, ...] = ("none", "intra_2opt", "relocate_2opt")
    initial_template_id: str = "cvrp_parallel_merge_static"
    initial_postprocess_mode: str = "none"
    planner_model: str = "deepseek-chat"
    eoh_model: str = "deepseek-chat"
    endpoint: str = "https://api.deepseek.com/v1/chat/completions"
    api_key_env: str = "DEEPSEEK_API_KEY"
    search_seed: int = 20261124
    dev_suite_id: str = "cvrp_dev_hetero_24"
    dev_split: str = "dev_train"
    use_benchmark_dev_suite: bool = False
    eval_dev_suite: bool = True
    dev_instance_count: int = 12
    dev_instance_size: int = 50
    agent_guidance: bool = True
    inject_static_kb_clues: bool = False
    tools_enabled: bool = True
    archive_feedback_enabled: bool = True
    kb_store_path: str | None = None
    checkpoint_budgets: tuple[int, ...] = (36,)
    mode: str = "mock"  # "mock" | "live"
    request_timeout_s: float = 60.0
    wall_seconds: float = 1200.0
    candidate_timeout_s: float = 20.0
    sandbox_timeout_s: float = 15.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AgentConfig":
        data = dict(raw)
        for key in ("allowed_templates", "allowed_postprocess_modes"):
            if key in data and isinstance(data[key], list):
                data[key] = tuple(str(x) for x in data[key])
        if "checkpoint_budgets" in data and isinstance(data["checkpoint_budgets"], list):
            data["checkpoint_budgets"] = tuple(int(x) for x in data["checkpoint_budgets"])
        return cls(**data)


@dataclass(frozen=True)
class EvidenceArtifactRef:
    path: str
    sha256: str
    kind: str = "diagnostic"

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "kind": self.kind}


@dataclass(frozen=True)
class HypothesisRecord:
    hypothesis_id: str
    round_id: int
    statement: str
    status: str
    rationale: str = ""
    evidence_artifacts: tuple[EvidenceArtifactRef, ...] = ()
    created_at_utc: str = field(default_factory=utc_now)
    updated_at_utc: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "round_id": int(self.round_id),
            "statement": self.statement,
            "status": self.status,
            "rationale": self.rationale,
            "evidence_artifacts": [e.as_dict() for e in self.evidence_artifacts],
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass
class AgentCheckpoint:
    schema_version: str = "m3-research-agent-checkpoint/v1"
    run_id: str = ""
    current_round: int = 1
    phase: str = "diagnose"  # diagnose | session_evolve | reflect | completed | budget_stopped
    round_step_index: int = 0
    round_outer_requests: int = 0
    round_reflect_requests: int = 0
    round_inner_requests: int = 0
    round_prev_best_dev: float | None = None
    round_plan_args: dict[str, Any] | None = None
    last_diag_ref: dict[str, Any] | None = None
    session_initialized: bool = False
    completed_rounds: list[int] = field(default_factory=list)
    active_template_id: str = "cvrp_parallel_merge_static"
    active_postprocess_mode: str = "none"
    best_solver_manifest_ref: str | None = None
    best_dev_objective: float | None = None
    best_all_feasible: bool = False
    best_completion_rate: float = 0.0
    frozen_checkpoints: dict[str, str] = field(default_factory=dict)
    round_summaries: list[dict[str, Any]] = field(default_factory=list)
    pending_reflect_payload: dict[str, Any] | None = None
    pending_submit_tool_call: dict[str, Any] | None = None
    updated_at_utc: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        self.updated_at_utc = utc_now()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AgentCheckpoint":
        return cls(**dict(raw))


RESULTS_TSV_HEADER = (
    "round_id\tarm_id\tproblem_family\ttemplate_id\tpostprocess_mode\t"
    "session_status\tbest_objective\tdelta_vs_prev\trequests_used_total\t"
    "outer_requests_round\tinner_requests_round\thypotheses_supported\t"
    "hypotheses_refuted\tfrozen_manifest_ref\n"
)


def append_results_tsv_row(tsv_path: Path, row: Mapping[str, Any]) -> None:
    tsv_path = Path(tsv_path)
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    if not tsv_path.is_file():
        atomic_write_text(tsv_path, RESULTS_TSV_HEADER)
    cols = [
        str(row.get("round_id", "")),
        str(row.get("arm_id", "")),
        str(row.get("problem_family", "")),
        str(row.get("template_id", "")),
        str(row.get("postprocess_mode", "")),
        str(row.get("session_status", "")),
        str(row.get("best_objective", "")),
        str(row.get("delta_vs_prev", "")),
        str(row.get("requests_used_total", "")),
        str(row.get("outer_requests_round", "")),
        str(row.get("inner_requests_round", "")),
        str(row.get("hypotheses_supported", 0)),
        str(row.get("hypotheses_refuted", 0)),
        str(row.get("frozen_manifest_ref", "")),
    ]
    line = "\t".join(cols) + "\n"
    with tsv_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
