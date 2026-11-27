"""Data contracts, configuration, and append-only audit helpers for ``research_agent``."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_skill_loop.interface_design.multiscale import MULTISCALE_DEFAULTS, multiscale_options

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


def effective_stagnation_diagnostic_mode(mode: str, enabled: bool) -> str:
    if mode not in ("off", "any", "slice_only", "sandbox_only"):
        raise ValueError("stagnation_diagnostic_mode_invalid")
    return "off" if mode == "any" and not enabled else mode


STAGNATION_DIAGNOSTIC_TOOLS = {
    "off": (),
    "any": ("diagnose_suite", "run_math_sandbox"),
    "slice_only": ("diagnose_suite",),
    "sandbox_only": ("run_math_sandbox",),
}


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
    strict_checkpoint_barriers: bool = False
    model_routing_policy: dict[str, Any] | None = None
    rate_card: dict[str, dict[str, float]] | None = None
    rate_card_version: str | None = None
    mode: str = "mock"  # "mock" | "live"
    request_timeout_s: float = 60.0
    wall_seconds: float = 1200.0
    candidate_timeout_s: float = 20.0
    sandbox_timeout_s: float = 15.0
    allow_extended_numpy_whitelist: bool = True
    enable_n200_latency_screen: bool = False
    enable_multiscale_latency_ratio_screen: bool = False
    max_n200_n100_ratio: float = 8.0
    multiscale_ratio_min_t200_ms: float = 10.0
    multiscale_n200_abs_cap_ms: float | None = None
    enable_degenerate_constant_screen: bool = False
    n200_latency_multiplier: float = 1.0
    enable_stagnation_diagnostic_gate: bool = False
    early_stop_no_jump_requests: int | None = None
    basin_restart_on_stagnation: bool = False
    memory_enabled: bool = False
    memory_store_path: str | None = None
    memory_mode: str = "off"
    kb_enabled: bool = True
    pinned_kb_release_id: str | None = None
    pinned_kb_manifest_sha256: str | None = None
    memory_max_solution_cards: int = 1
    memory_mmr_lambda: float = 0.7
    memory_cooldown_rounds: int = 2
    memory_online_writeback_enabled: bool = True
    stagnation_diagnostic_mode: str = "any"
    template_version: str = "v1"
    enable_c2_joint_screen: bool = False
    global_early_stop_mode: str = "off"
    global_early_stop_patience: int = 24
    risk_stop_window: int = 32
    risk_stop_prior_a: float = 0.5
    risk_stop_prior_b: float = 19.5
    risk_stop_eps: float = 0.0010
    risk_stop_alpha: float = 0.15
    risk_stop_d_floor: float = 0.002
    risk_stop_min_requests: int = 30
    risk_stop_cooldown: int = 18
    strict_diagnostic_gate: bool = False
    require_c2_multiscale_admission: bool = False

    def __post_init__(self) -> None:
        effective_stagnation_diagnostic_mode(
            self.stagnation_diagnostic_mode, self.enable_stagnation_diagnostic_gate
        )
        for name in ("strict_diagnostic_gate", "require_c2_multiscale_admission"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name}_must_be_boolean")
        multiscale_options({
            **{name: getattr(self, name) for name in MULTISCALE_DEFAULTS},
            "enable_n200_latency_screen": self.enable_n200_latency_screen,
        })
        multiplier = self.n200_latency_multiplier
        if type(multiplier) not in {float, int} or not math.isfinite(multiplier) or multiplier <= 0:
            raise ValueError("n200_latency_multiplier_must_be_positive_finite")
        threshold = self.early_stop_no_jump_requests
        if threshold is not None and (type(threshold) is not int or threshold < 0):
            raise ValueError("early_stop_no_jump_requests_must_be_nonnegative_integer")
        if self.template_version not in ("v1", "v2"):
            raise ValueError("template_version_invalid")
        if type(self.enable_c2_joint_screen) is not bool:
            raise ValueError("enable_c2_joint_screen_must_be_boolean")
        if self.enable_c2_joint_screen and self.problem_family != "cvrp":
            raise ValueError("c2_joint_screen_requires_cvrp")
        if self.global_early_stop_mode not in ("off", "naive_patience", "risk_bounded_beta_geom"):
            raise ValueError("global_early_stop_mode_invalid")
        for name, minimum in (
            ("global_early_stop_patience", 1), ("risk_stop_window", 1),
            ("risk_stop_min_requests", 0), ("risk_stop_cooldown", 0),
        ):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name}_out_of_range")
        for name in ("risk_stop_prior_a", "risk_stop_prior_b", "risk_stop_eps", "risk_stop_alpha", "risk_stop_d_floor"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name}_must_be_nonnegative_finite")
        if self.risk_stop_prior_a == 0 or self.risk_stop_prior_b == 0 or self.risk_stop_alpha > 1:
            raise ValueError("risk_stop_prior_or_alpha_out_of_range")
        if self.memory_mode not in ("off", "naive_static", "m35_l12", "m35_full"):
            raise ValueError("memory_mode_invalid")
        if type(self.memory_enabled) is not bool or type(self.kb_enabled) is not bool:
            raise ValueError("memory_and_kb_enabled_must_be_boolean")
        if type(self.memory_online_writeback_enabled) is not bool:
            raise ValueError("memory_online_writeback_enabled_must_be_boolean")
        if type(self.memory_max_solution_cards) is not int or not 0 <= self.memory_max_solution_cards <= 1:
            raise ValueError("memory_max_solution_cards_out_of_range")
        if type(self.memory_mmr_lambda) not in (int, float) or not 0 <= self.memory_mmr_lambda <= 1:
            raise ValueError("memory_mmr_lambda_out_of_range")
        if type(self.memory_cooldown_rounds) is not int or self.memory_cooldown_rounds < 0:
            raise ValueError("memory_cooldown_rounds_must_be_nonnegative_integer")
        release, digest = self.pinned_kb_release_id, self.pinned_kb_manifest_sha256
        if (release is None) != (digest is None):
            raise ValueError("pinned_kb_release_and_digest_required")
        if release is not None and (
            not isinstance(release, str) or not release.strip()
            or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise ValueError("pinned_kb_release_or_digest_invalid")

    @property
    def effective_early_stop_no_jump_requests(self) -> int | None:
        if self.global_early_stop_mode == "naive_patience" and not self.basin_restart_on_stagnation:
            return self.global_early_stop_patience
        return self.early_stop_no_jump_requests

    def version_for_template(self, template_id: str) -> str:
        return self.template_version if template_id == "cvrp_parallel_merge_static" else "v1"

    @property
    def effective_stagnation_diagnostic_mode(self) -> str:
        if not self.tools_enabled:
            return "off"
        return effective_stagnation_diagnostic_mode(
            self.stagnation_diagnostic_mode, self.enable_stagnation_diagnostic_gate
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for name in ("strict_diagnostic_gate", "require_c2_multiscale_admission"):
            if not data[name]:
                del data[name]
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AgentConfig":
        data = dict(raw)
        for key in ("allowed_templates", "allowed_postprocess_modes"):
            if key in data and isinstance(data[key], list):
                data[key] = tuple(str(x) for x in data[key])
        if "checkpoint_budgets" in data and isinstance(data["checkpoint_budgets"], list):
            data["checkpoint_budgets"] = tuple(int(x) for x in data["checkpoint_budgets"])
        for map_key in ("model_routing_policy", "rate_card"):
            if map_key in data and isinstance(data[map_key], Mapping):
                data[map_key] = dict(data[map_key])
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
    auto_registered: bool = False

    def to_dict(self) -> dict[str, Any]:
        record = {
            "hypothesis_id": self.hypothesis_id,
            "round_id": int(self.round_id),
            "statement": self.statement,
            "status": self.status,
            "rationale": self.rationale,
            "evidence_artifacts": [e.as_dict() for e in self.evidence_artifacts],
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }
        if self.auto_registered:
            record["auto_registered"] = True
        return record


@dataclass
class AgentCheckpoint:
    schema_version: str = "m3-research-agent-checkpoint/v1"
    run_id: str = ""
    current_round: int = 1
    phase: str = "diagnose"  # Also supports the terminal phase early_stopped_global.
    round_step_index: int = 0
    round_outer_requests: int = 0
    round_reflect_requests: int = 0
    round_reflection_finished: bool = False
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
    accumulated_wall_seconds: float = 0.0
    updated_at_utc: str = field(default_factory=utc_now)
    round_diagnostic_called: bool = False
    diagnostic_ever_called: bool = False
    round_diagnostic_blocks: int = 0
    consecutive_stagnant_rounds: int = 0
    trajectory_best_dev_objective: float | None = None
    restart_eligible_round_id: int | None = None
    trajectory_control_events: list[dict[str, Any]] = field(default_factory=list)
    last_sandbox_ref: dict[str, Any] | None = None
    sandbox_run_refs: list[dict[str, Any]] = field(default_factory=list)
    sandbox_success_count: int = 0
    gate_bypass_count: int = 0
    gate_bypass_events: list[dict[str, Any]] = field(default_factory=list)

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
    existing = tsv_path.read_text(encoding="utf-8") if tsv_path.is_file() else RESULTS_TSV_HEADER
    # Reflection may resume after writing the TSV and before the checkpoint commits.
    if not existing.endswith("\n" + line):
        atomic_write_text(tsv_path, existing + line)
