"""Bridge connecting dynamic multi-problem interfaces into the cross-harness Skill + Session Runtime.

Supports CVRP (L1/L2a/L2b/L3/L3b dual-hook), M3.1 TSP/OBP/BPP, M3.2 settled-prefix
checkpoint barriers, deterministic OpenCode Go strong/weak routing, and 2000ms timeouts.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from eoh.eoh.eoh import EOH

from agent_skill_loop.contracts import EOH_COMMIT, EvaluationResult, SkillVersion
from agent_skill_loop.evidence.behavior import BehaviorTraceRecorder
from agent_skill_loop.milestone_checkpoint import (
    claim_latest_pending_attempt_token,
    get_run_wall_offset_seconds,
    settle_attempt_provenance,
    settle_pending_provenance_for_terminal_requests,
    try_seal_draining_checkpoints,
)
from agent_skill_loop.request_budget import BudgetExhausted
from agent_skill_loop.session_ledger import SessionRequestBudget, solver_event
from agent_skill_loop.skill_store import _atomic_write_text, load_skill, save_skill
from knowledge_tools.core import resolve_release

from .contracts import ALLOWED_POSTPROCESS_MODES, FrozenInterfaceSolver, InterfaceDesign, sha256_text
from .dynamic_eoh import (
    DEFAULT_MOCK_MERGE_CANDIDATES,
    DynamicInterfaceProblem,
    MockEoHLLMServer,
    _DynamicCandidateEoH,
    _default_mock_candidates,
    derive_effective_batch_timeout_s,
)
from .model_routing import ModelRoutingPolicy, allocate_logical_route, compute_attempt_cost_usd, extract_provider_usage
from .planner import KB_ROUND_CONTEXT_BY_TEMPLATE, build_design_for_template, parse_hook_candidate
from .runtime import resolve_problem_adapter, validate_hook_ast
from .templates import get_template_spec
from .validator import InterfaceValidator

_REPO_ROOT = Path(__file__).resolve().parents[2]

INTERFACE_SELECTION_KEYS = frozenset({
    "template_id",
    "template_version",
    "postprocess_mode",
    "template_options",
    "time_budget_ms",
    "cited_kb_ids",
    "diagnostic_ref",
    "rationale",
    "fresh_template",
})


def _utc_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_positive_budget_ms(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name}_must_be_number")
    val = float(value)
    if not math.isfinite(val) or val <= 0.0:
        raise ValueError(f"{field_name}_must_be_positive")
    return val


def _early_stop_limit(options: Mapping[str, Any]) -> int:
    value = options.get("early_stop_no_jump_requests")
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("early_stop_no_jump_requests_must_be_nonnegative_integer")
    return value


def resolve_session_time_budget_ms(
    selection: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    design: InterfaceDesign | None = None,
) -> float:
    """Resolve one consistent per-instance solve budget (ms) across submit/execute/revalidate."""
    cfg_val: float | None = None
    sel_val: float | None = None
    opt_val: float | None = None

    if isinstance(config, Mapping) and config.get("instance_time_budget_ms") is not None:
        cfg_val = _validate_positive_budget_ms(config["instance_time_budget_ms"], field_name="instance_time_budget_ms")
    if isinstance(selection, Mapping) and selection.get("time_budget_ms") is not None:
        sel_val = _validate_positive_budget_ms(selection["time_budget_ms"], field_name="interface_selection_time_budget_ms")
    if design is not None and design.template_options.get("time_budget_ms") is not None:
        opt_val = _validate_positive_budget_ms(design.template_options["time_budget_ms"], field_name="template_options_time_budget_ms")

    if cfg_val is not None and sel_val is not None and abs(cfg_val - sel_val) > 1e-6:
        raise ValueError(f"session_time_budget_mismatch:config={cfg_val}:selection={sel_val}")
    if cfg_val is not None:
        return cfg_val
    if sel_val is not None:
        return sel_val
    if opt_val is not None:
        return opt_val
    return 500.0


def resolve_session_kb_release(
    config: Mapping[str, Any] | None = None,
    *,
    session_root: Path | None = None,
    repo_root: Path = _REPO_ROOT,
) -> tuple[str, str]:
    """Resolve and session-lock the active KB release ID and manifest SHA-256."""
    if isinstance(config, Mapping) and config.get("kb_release_id") and config.get("kb_manifest_sha256"):
        return str(config["kb_release_id"]), str(config["kb_manifest_sha256"])

    lock_path = (Path(session_root) / "kb_release_lock.json") if session_root is not None else None
    if lock_path is not None and lock_path.is_file():
        locked = json.loads(lock_path.read_text(encoding="utf-8"))
        return str(locked["kb_release_id"]), str(locked["kb_manifest_sha256"])

    target: Path | None = None
    if isinstance(config, Mapping):
        if config.get("kb_release_path"):
            target = Path(str(config["kb_release_path"]))
        elif config.get("kb_release_id"):
            cand = repo_root / "knowledge_store" / "releases" / str(config["kb_release_id"])
            if cand.exists():
                target = cand
    if target is None:
        target = repo_root / "knowledge_store" / "current"

    rel_dir = resolve_release(target)
    manifest_path = rel_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_obj = json.loads(manifest_bytes)
    rel_id = str(manifest_obj.get("release_id") or rel_dir.name)

    if lock_path is not None:
        payload = json.dumps(
            {
                "kb_release_id": rel_id,
                "kb_manifest_sha256": manifest_sha,
                "release_dir": str(rel_dir),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        _atomic_write_text(lock_path, payload)
    return rel_id, manifest_sha


def parse_interface_selection(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly parse optional ``plan.interface_selection`` submitted to ``session submit-plan``."""
    if not isinstance(raw, Mapping):
        raise ValueError("interface_selection_must_be_object")
    unknown = set(raw) - INTERFACE_SELECTION_KEYS
    if unknown:
        raise ValueError(f"interface_selection_unknown_fields:{','.join(sorted(unknown))}")
    tid = raw.get("template_id")
    tver = raw.get("template_version", "v1")
    if not isinstance(tid, str) or not tid.strip():
        raise ValueError("interface_selection_template_id_required")
    if not isinstance(tver, str) or not tver.strip():
        raise ValueError("interface_selection_template_version_required")
    tid = tid.strip()
    tver = tver.strip()
    try:
        tpl = get_template_spec(tid, tver)
    except KeyError:
        raise ValueError(f"interface_selection_unknown_template:{tid}/{tver}") from None

    post_mode = str(raw.get("postprocess_mode", "none")).strip()
    if post_mode not in ALLOWED_POSTPROCESS_MODES or post_mode not in tpl.allowed_postprocess_modes:
        raise ValueError(f"interface_selection_postprocess_not_allowed:{post_mode}")

    opts = raw.get("template_options")
    if opts is None:
        opts = {}
    elif not isinstance(opts, Mapping):
        raise ValueError("interface_selection_template_options_must_be_object")
    else:
        opts = dict(opts)
    for name in (
        "allow_extended_numpy_whitelist", "enable_n200_latency_screen", "enable_degenerate_constant_screen",
    ):
        if name in opts and not isinstance(opts[name], bool):
            raise ValueError(f"interface_selection_{name}_must_be_boolean")
    if "n200_latency_multiplier" in opts:
        opts["n200_latency_multiplier"] = _validate_positive_budget_ms(
            opts["n200_latency_multiplier"], field_name="n200_latency_multiplier",
        )
    _early_stop_limit(opts)
    fresh_template = raw.get("fresh_template", False)
    if not isinstance(fresh_template, bool):
        raise ValueError("interface_selection_fresh_template_must_be_boolean")

    cited = raw.get("cited_kb_ids", [])
    if not isinstance(cited, list) or any(not isinstance(x, str) or not x.strip() for x in cited):
        raise ValueError("interface_selection_cited_kb_ids_must_be_string_list")

    diag_ref = raw.get("diagnostic_ref")
    if diag_ref is not None and not isinstance(diag_ref, Mapping):
        raise ValueError("interface_selection_diagnostic_ref_must_be_object")

    rationale = str(raw.get("rationale") or "").strip()
    if len(rationale) > 2048:
        raise ValueError("interface_selection_rationale_too_large")

    parsed: dict[str, Any] = {
        "template_id": tid,
        "template_version": tver,
        "postprocess_mode": post_mode,
        "template_options": opts,
        "cited_kb_ids": [x.strip() for x in cited],
        "diagnostic_ref": dict(diag_ref) if isinstance(diag_ref, Mapping) else None,
        "rationale": rationale,
    }
    if raw.get("time_budget_ms") is not None:
        parsed["time_budget_ms"] = _validate_positive_budget_ms(
            raw["time_budget_ms"], field_name="interface_selection_time_budget_ms"
        )
    if fresh_template:
        parsed["fresh_template"] = True
    return parsed


def validate_session_interface_selection(
    selection: Mapping[str, Any],
    *,
    round_id: int,
    candidate_timeout_s: float = 20.0,
    instance_time_budget_ms: float = 500.0,
) -> tuple[InterfaceDesign, dict[str, Any]]:
    """Build ``InterfaceDesign`` from ``plan.interface_selection`` and run all 5 behavioral gates."""
    tid = str(selection["template_id"])
    tver = str(selection.get("template_version", "v1"))
    post_mode = str(selection.get("postprocess_mode", "none"))
    design = build_design_for_template(
        tid,
        tver,
        design_id=f"session_r{round_id:04d}_{tid}_{tver}",
        postprocess_mode=post_mode,
        diagnostic_ref=selection.get("diagnostic_ref"),
        rationale=str(selection.get("rationale") or f"Session round {round_id} interface selection."),
    )
    if selection.get("cited_kb_ids") or selection.get("template_options"):
        design = InterfaceDesign(
            design_id=design.design_id,
            problem_family=design.problem_family,
            paradigm=design.paradigm,
            template_id=design.template_id,
            template_version=design.template_version,
            postprocess_mode=design.postprocess_mode,
            hook_name=design.hook_name,
            hook_signature=design.hook_signature,
            hook_task_description=design.hook_task_description,
            baseline_hook_code=design.baseline_hook_code,
            cited_kb_ids=tuple(selection.get("cited_kb_ids") or design.cited_kb_ids),
            diagnostic_ref=design.diagnostic_ref,
            rationale=design.rationale,
            template_options={**design.template_options, **dict(selection.get("template_options") or {})},
            protocol_id=design.protocol_id,
            hook_specs=design.hook_specs,
            hook_implementations=dict(design.hook_implementations),
        )
    validator = InterfaceValidator(
        candidate_timeout_s=candidate_timeout_s,
        instance_time_budget_ms=instance_time_budget_ms,
        outer_timeout_s=candidate_timeout_s,
    )
    report = validator.validate(design)
    return design, report.as_dict()


def _normalize_session_suite_instances(
    suite: Mapping[str, Any], *, problem_family: str = "cvrp",
) -> list[dict[str, Any]]:
    """Adapt a Session dev_suite.json into the target problem family's runtime instance shape."""
    out: list[dict[str, Any]] = []
    for idx, inst in enumerate(suite.get("instances") or []):
        iid = str(inst.get("instance_id") or f"session_inst_{idx:03d}")
        if problem_family == "tsp":
            coords = inst.get("coordinates")
            if coords is None:
                raise ValueError("session_suite_missing_tsp_coordinates")
            row = {
                "instance_id": iid,
                "protocol_id": inst.get("protocol_id") or "tsp/v1",
                "coordinates": [list(pt) for pt in coords],
                "size": len(coords),
            }
            if inst.get("reference_objective") is not None:
                row["reference_objective"] = inst["reference_objective"]
            out.append(row)
            continue
        if problem_family in {"obp", "bpp"}:
            default_proto = "obp_online/v1" if problem_family == "obp" else "bpp_offline/v1"
            row = {
                "instance_id": iid,
                "protocol_id": inst.get("protocol_id") or default_proto,
                "items": list(inst["items"]),
                "capacity": float(inst["capacity"]),
                "size": len(inst["items"]),
            }
            if inst.get("reference_objective") is not None:
                row["reference_objective"] = inst["reference_objective"]
            out.append(row)
            continue
        coords = inst.get("customer_coordinates") or inst.get("coordinates")
        if coords is None:
            raise ValueError("session_suite_missing_customer_coordinates")
        depot = inst.get("depot")
        if depot is None:
            depot = coords[0]
            cust_coords = coords[1:]
            raw_demands = list(inst["demands"])[1:] if len(inst["demands"]) == len(coords) else list(inst["demands"])
        else:
            cust_coords = coords
            raw_demands = list(inst["demands"])
        row = {
            "instance_id": iid,
            "size": len(cust_coords),
            "depot": list(depot),
            "customer_coordinates": [list(pt) for pt in cust_coords],
            "demands": [float(d) for d in raw_demands],
            "capacity": float(inst["capacity"]),
        }
        if inst.get("reference_objective") is not None:
            row["reference_objective"] = inst["reference_objective"]
        out.append(row)
    return out


def load_verified_session_design(root: Path, receipt: Mapping[str, Any]) -> InterfaceDesign:
    """Check files against the successful submit-plan receipt held in SQLite."""
    def read(ref_key: str, hash_key: str) -> dict[str, Any]:
        path = (root / receipt[ref_key]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("interface_receipt_path_outside_session")
        text = path.read_text(encoding="utf-8")
        if sha256_text(text) != receipt[hash_key]:
            raise ValueError(f"interface_receipt_hash_mismatch:{ref_key}")
        return json.loads(text)

    design = InterfaceDesign.from_dict(read("design_ref", "design_file_sha256"))
    validation = read("validation_ref", "validation_sha256")
    template = get_template_spec(design.template_id, design.template_version)
    if (
        design.design_sha256 != receipt["design_sha256"]
        or validation.get("design_sha256") != design.design_sha256
        or validation.get("template_source_sha256") != template.template_source_sha256
        or not validation.get("passed")
    ):
        raise ValueError("interface_design_validation_identity_mismatch")
    return design


def _summarize_records_for_checkpoint(
    instances: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    *,
    dev_suite_hash: str,
    solve_budget_ms: float,
) -> dict[str, Any]:
    valid_vals: list[float] = []
    pen_vals: list[float] = []
    for inst, rec in zip(instances, records):
        obj = rec.get("objective")
        if obj is None:
            obj = rec.get("tour_length")
        if obj is None:
            obj = rec.get("bins_used")
        if rec.get("valid") is True and rec.get("completed", True) is True and obj is not None:
            valid_vals.append(float(obj))
            pen_vals.append(float(obj))
        else:
            ref = inst.get("reference_objective")
            pen_vals.append(2.0 * float(ref) if isinstance(ref, (int, float)) and float(ref) > 0 else 100.0)
    n_total = len(instances)
    valid_count = len(valid_vals)
    comp_rate = round(valid_count / max(1, n_total), 6)
    return {
        "all_feasible": bool(n_total > 0 and valid_count == n_total),
        "completion_rate": comp_rate,
        "penalized_mean_objective": round(sum(pen_vals) / max(1, n_total), 8),
        "valid_only_mean_objective": round(sum(valid_vals) / valid_count, 8) if valid_vals else None,
        "dev_suite_hash": dev_suite_hash,
        "solve_budget_ms": float(solve_budget_ms),
    }


class _SessionTrackedDynamicProblem(DynamicInterfaceProblem):
    """DynamicInterfaceProblem mirroring evaluations into Session SQLite & M3.2 milestone ledger."""

    def __init__(
        self,
        *,
        session: dict[str, Any],
        problem_id: str,
        suite_hash: str,
        evaluator_hash: str,
        metric_spec_hash: str | None = None,
        problem_spec_hash: str | None = None,
        data_manifest_hash: str | None = None,
        kb_release_id: str = "",
        milestone_ledger_path: Path | None = None,
        milestone_run_id: str | None = None,
        strict_checkpoint_barriers: bool = False,
        run_started_monotonic: float | None = None,
        bridge_ref: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(suite_hash=suite_hash, **kwargs)
        self.session = session
        self.session_problem_id = problem_id
        self.session_evaluator_hash = evaluator_hash
        self.session_metric_spec_hash = metric_spec_hash
        self.session_problem_spec_hash = problem_spec_hash
        self.session_data_manifest_hash = data_manifest_hash
        self.kb_release_id = kb_release_id
        self.milestone_ledger_path = Path(milestone_ledger_path) if milestone_ledger_path else None
        self.milestone_run_id = milestone_run_id
        self.strict_checkpoint_barriers = bool(strict_checkpoint_barriers)
        self.run_started_monotonic = run_started_monotonic
        self.bridge_ref = bridge_ref
        self.seed_origins: dict[str, str] = {}
        self._seq = 0
        self._val_cache: dict[str, bool] = {}

    def __getstate__(self) -> dict[str, Any]:
        state = super().__getstate__()
        state["bridge_ref"] = None
        return state

    def _start_generated_evaluations(self) -> None:
        super()._start_generated_evaluations()
        self.seed_origins.clear()

    def evaluate_detailed(self, code_string: str) -> dict[str, Any]:
        self._seq += 1
        eval_id = uuid.uuid4().hex
        code_str = str(code_string)
        code_sha = sha256_text(code_str)
        origin = self.seed_origins.get(code_sha, "generated")
        cand_id = origin if origin in {"baseline", "explicit_parent"} else f"m2_cand_{self._seq}"

        attempt_token = None
        if origin == "generated":
            if self.bridge_ref is not None and hasattr(self.bridge_ref, "consume_pending_attempt_token"):
                attempt_token = self.bridge_ref.consume_pending_attempt_token()
            elif self.strict_checkpoint_barriers and self.milestone_ledger_path is not None and self.milestone_run_id:
                attempt_token = claim_latest_pending_attempt_token(
                    self.milestone_ledger_path,
                    self.milestone_run_id,
                    eval_id=eval_id,
                )

        start_payload = {
            "code": code_str,
            "code_sha256": code_sha,
            "problem": self.session_problem_id,
            "entrypoint": self.design.hook_name,
            "evaluator_hash": self.session_evaluator_hash,
            "origin": origin,
            "candidate_id": cand_id,
            "revision": "original",
            "pid": os.getpid(),
            "suite_hash": self.suite_hash,
            "evaluation_id": eval_id,
            "metric_spec_hash": self.session_metric_spec_hash,
            "problem_spec_hash": self.session_problem_spec_hash,
            "data_manifest_hash": self.session_data_manifest_hash,
            "evaluation": None,
        }
        solver_event(self.session, start_payload)

        prev_origin = getattr(self, "_current_eval_origin", None)
        self._current_eval_origin = origin
        try:
            super_eval = super().evaluate_detailed
            params = inspect.signature(super_eval).parameters
            if "origin" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                resp = super_eval(code_str, origin=origin)
            else:
                resp = super_eval(code_str)
        finally:
            self._current_eval_origin = prev_origin
        inst_objs = tuple(float(x) for x in (resp.get("instance_objectives") or []))
        if resp.get("valid") and inst_objs:
            exact_obj = sum(inst_objs) / len(inst_objs)
        elif resp.get("valid") and resp.get("objective") is not None:
            exact_obj = float(resp["objective"])
        else:
            exact_obj = None
        metrics: dict[str, Any] = {}
        if records := resp.get("records"):
            recorder = BehaviorTraceRecorder(
                contract={
                    "mode": "dynamic_interface_instance_profile/v1",
                    "template_id": self.design.template_id,
                    "template_version": self.design.template_version,
                    "postprocess_mode": self.design.postprocess_mode,
                    "solve_deadline_ms": self.instance_time_budget_ms,
                },
                suite_hash=self.suite_hash,
            )
            complete = bool(resp.get("valid"))
            for index, record in enumerate(records):
                completed = record.get("completed") is True
                complete &= completed
                recorder.begin_instance(instance_id=str(record.get("instance_id", "")), instance_index=index)
                obj = record.get("objective")
                recorder.record({
                    "outcome_class": record.get("outcome_class"),
                    "feasible": record.get("feasible", record.get("valid")),
                    "completed": completed,
                    "exact_k_feasible": record.get("exact_k_feasible", record.get("exact_vehicle_count")),
                    "route_count": record.get("route_count"),
                    "objective_r6": round(float(obj), 6) if obj is not None and math.isfinite(obj) else None,
                })
                recorder.finish_instance(status="complete" if completed else "partial")
            metrics["behavior_evidence"] = recorder.finalize(status="complete" if complete else "partial")
        if "n200_latency_diagnostics" in resp:
            metrics["n200_latency_diagnostics"] = resp["n200_latency_diagnostics"]
        ev_result = EvaluationResult(
            valid=bool(resp.get("valid")),
            objective=exact_obj,
            instance_objectives=inst_objs,
            suite_hash=self.suite_hash,
            error_code=resp.get("error_code"),
            error_detail=resp.get("error_detail"),
            elapsed_seconds=float(resp.get("worker_wall_ms") or 0.0) / 1000.0,
            metrics=metrics or None,
        )
        done_payload = {
            **start_payload,
            "evaluation": ev_result.as_dict(),
            "template_id": self.design.template_id,
            "template_version": self.design.template_version,
            "template_source_sha256": self.tpl.template_source_sha256,
            "design_sha256": self.design.design_sha256,
            "attempt_token": attempt_token,
        }
        if self.evaluation_log:
            ev_path = Path(self.evaluation_log)
            ev_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_lock:
                with ev_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(done_payload, ensure_ascii=False, allow_nan=False) + "\n")
                    handle.flush()
        solver_event(self.session, done_payload)

        if self.strict_checkpoint_barriers and self.milestone_ledger_path is not None and self.milestone_run_id:
            if attempt_token is not None:
                if ev_result.valid and ev_result.objective is not None:
                    try:
                        primary_code, impls = self._resolve_hook_payload(code_str)
                    except (ValueError, SyntaxError):
                        primary_code, impls = None, None
                    if primary_code is None:
                        settle_attempt_provenance(
                            self.milestone_ledger_path,
                            attempt_token=attempt_token,
                            generation_status="malformed_response",
                            eval_id=eval_id,
                            code_sha256=code_sha,
                            validation_passed=False,
                        )
                    else:
                        if code_sha not in self._val_cache:
                            validator = InterfaceValidator(
                                candidate_timeout_s=self.candidate_timeout_s,
                                instance_time_budget_ms=self.instance_time_budget_ms,
                                outer_timeout_s=self.candidate_timeout_s,
                            )
                            vrep = validator.validate(
                                self.design,
                                hook_code_override=primary_code,
                                hook_implementations=impls,
                            )
                            self._val_cache[code_sha] = bool(vrep.passed)
                        passed = self._val_cache[code_sha]
                        dev_summary = _summarize_records_for_checkpoint(
                            self.instances,
                            resp.get("records") or [],
                            dev_suite_hash=self.suite_hash or "",
                            solve_budget_ms=self.instance_time_budget_ms,
                        )
                        frozen_manifest = FrozenInterfaceSolver(
                            solver_id=f"ckpt_cand_{code_sha[:10]}",
                            display_name=f"M3.2 Candidate {self.design.template_id} ({code_sha[:8]})",
                            problem_family=self.design.problem_family,
                            paradigm=self.design.paradigm,
                            template_id=self.design.template_id,
                            template_version=self.design.template_version,
                            template_source_sha256=self.tpl.template_source_sha256,
                            postprocess_mode=self.design.postprocess_mode,
                            template_options=dict(self.design.template_options),
                            hook_name=self.design.hook_name,
                            hook_code=primary_code,
                            hook_code_sha256=sha256_text(primary_code),
                            design_sha256=self.design.design_sha256,
                            origin_run=str(self.milestone_run_id),
                            kb_release_id=self.kb_release_id,
                            kb_entry_id=self.design.cited_kb_ids[0] if self.design.cited_kb_ids else None,
                            cited_kb_ids=self.design.cited_kb_ids,
                            diagnostic_ref=self.design.diagnostic_ref,
                            description=f"Settled candidate under {self.design.template_id}/{self.design.template_version}.",
                            default_budget_ms=self.instance_time_budget_ms,
                            protocol_id=self.adapter.protocol_id,
                            hook_specs=self.tpl.hook_specs,
                            hook_implementations=impls or {},
                        )
                        settle_attempt_provenance(
                            self.milestone_ledger_path,
                            attempt_token=attempt_token,
                            generation_status="valid_candidate",
                            eval_id=eval_id,
                            code_sha256=code_sha,
                            bundle_hash=frozen_manifest.bundle_hash,
                            solver_manifest=frozen_manifest.to_dict(),
                            validation_passed=passed,
                            dev_eval=dev_summary,
                            dev_suite_hash=self.suite_hash,
                            solve_budget_ms=self.instance_time_budget_ms,
                        )
                else:
                    settle_attempt_provenance(
                        self.milestone_ledger_path,
                        attempt_token=attempt_token,
                        generation_status="invalid_candidate",
                        eval_id=eval_id,
                        code_sha256=code_sha,
                        validation_passed=False,
                    )
            wall_elapsed = (time.monotonic() - self.run_started_monotonic) if self.run_started_monotonic is not None else None
            try_seal_draining_checkpoints(
                self.milestone_ledger_path,
                self.milestone_run_id,
                wall_elapsed_seconds=wall_elapsed,
            )
        return resp

    def _append_eval_log(self, code_string: str, resp: Mapping[str, Any]) -> None:
        return None


class StagnationEarlyStop(Exception):
    """Internal signal for a completed search stopped by the no-improvement limit."""


class _StagnationAwareEoH(_DynamicCandidateEoH):
    """Check the durable evaluation journal between official EoH sample claims."""

    def __init__(self, config: Any, problem: DynamicInterfaceProblem, *, evaluation_log: Path, no_jump_limit: int) -> None:
        super().__init__(config, problem)
        if self.num_samplers != 1 or self.num_evaluators != 1:
            raise ValueError("stagnation_early_stop_requires_serial_sampling")
        self.evaluation_log = evaluation_log
        self.no_jump_limit = no_jump_limit
        self.no_jump_count = 0
        self._trajectory_error: Exception | None = None

    def _sampler_worker(self, population_ref: list, target: int, t0: float) -> None:
        best_key: tuple[int, float] = (-1, -math.inf)
        seen: set[str] = set()

        def consume_rows(rows: Iterable[str]) -> None:
            nonlocal best_key
            for line in rows:
                row = json.loads(line)
                evaluation_id = row["evaluation_id"]
                if evaluation_id in seen:
                    continue
                seen.add(evaluation_id)
                evaluation = row["evaluation"]
                objective = evaluation.get("objective")
                be_status = (evaluation.get("metrics") or {}).get("behavior_evidence", {}).get("status")
                is_complete = int(bool(evaluation.get("completed", True)) and be_status != "partial")
                cand_key = (
                    (is_complete, -float(objective))
                    if (evaluation.get("valid") and objective is not None and math.isfinite(objective))
                    else None
                )
                improved = cand_key is not None and cand_key > best_key
                if improved:
                    best_key = cand_key
                if row["origin"] == "generated":
                    self.no_jump_count = 0 if improved else self.no_jump_count + 1

        try:
            with self.evaluation_log.open(encoding="utf-8") as journal:
                consume_rows(journal)
                # EoH registers the offspring before this call returns. Limit each
                # invocation to one claim so the triggering sample is retained.
                for sample_target in range(1, target + 1):
                    super()._sampler_worker(population_ref, sample_target, t0)
                    consume_rows(journal)
                    if self.no_jump_count >= self.no_jump_limit:
                        return
        except Exception as exc:
            self._trajectory_error = exc

    def run(self) -> None:
        super().run()
        if self._trajectory_error is not None:
            raise self._trajectory_error
        if self.no_jump_count >= self.no_jump_limit:
            raise StagnationEarlyStop


def _build_session_bridge(
    *,
    endpoint: str,
    api_key: str,
    model: str,
    request_timeout: float,
    budget: SessionRequestBudget,
    req_log: Path,
    wall_seconds: float,
    problem: str,
    routing_policy: ModelRoutingPolicy,
    ledger_path: Path | None,
    run_id: str,
    strict_barriers: bool,
    use_mock: bool,
    mock_candidates: Sequence[str],
    mock_failure_hook: Any | None = None,
    run_started_monotonic: float,
):
    from agent_skill_loop.client import ProviderFailure, http_post_with_deadline
    from eoh_frozen.generation_contract import generation_parameters
    from eoh_frozen.llm_bridge import OpenAIPathBridge

    class _RoutedSessionBridge(OpenAIPathBridge):
        """Session bridge supporting pre-payload routing, rate-card usage, and M3.2 prefix barriers."""

        def __init__(self) -> None:
            super().__init__(
                endpoint,
                api_key,
                model,
                timeout=request_timeout,
                budget=budget,
                request_log=req_log,
                wall_seconds=wall_seconds,
                problem=problem,
            )
            self._routing_policy = routing_policy
            self._ledger_path = Path(ledger_path) if ledger_path else None
            self._run_id = run_id
            self._strict_barriers = bool(strict_barriers)
            self._use_mock = bool(use_mock)
            self._mock_candidates = list(mock_candidates)
            self._mock_idx = 0
            self._mock_failure_hook = mock_failure_hook
            self._pending_attempt_token: str | None = None
            self._token_lock = threading.Lock()
            self._run_started = run_started_monotonic

        def consume_pending_attempt_token(self) -> str | None:
            with self._token_lock:
                tok = self._pending_attempt_token
                self._pending_attempt_token = None
                return tok

        def settle_trailing_pending(self, reason: str = "eoh_skipped") -> None:
            tok = self.consume_pending_attempt_token()
            if tok is not None and self._ledger_path is not None:
                settle_attempt_provenance(
                    self._ledger_path,
                    attempt_token=tok,
                    generation_status=reason,
                    only_if_pending=True,
                )
            if self._strict_barriers and self._ledger_path is not None:
                settle_pending_provenance_for_terminal_requests(self._ledger_path, self._run_id)
                try_seal_draining_checkpoints(
                    self._ledger_path,
                    self._run_id,
                    wall_elapsed_seconds=time.monotonic() - self._run_started,
                )

        def _save_exchange(self, slot, prompt: str, response: str, *, metadata=None) -> None:
            if slot is not None:
                slot.response_sha256 = hashlib.sha256(str(response).encode("utf-8")).hexdigest()
            super()._save_exchange(slot, prompt, response, metadata=metadata)

        def _perform_post(
            self, target_url: str, headers: dict[str, str], body_bytes: bytes, timeout_s: float, *, slot, prompt: str,
        ) -> tuple[int, bytes]:
            if not self._use_mock:
                return http_post_with_deadline(target_url, headers, body_bytes, timeout_s)
            if callable(self._mock_failure_hook):
                hook_res = self._mock_failure_hook(slot, json.loads(body_bytes.decode("utf-8")), prompt)
                if hook_res is not None:
                    return hook_res
            if prompt.strip() == "1+1=?":
                text = "2"
            else:
                text = self._mock_candidates[self._mock_idx % len(self._mock_candidates)]
                self._mock_idx += 1
            mock_resp = {
                "id": f"mock_{slot.request_id if slot else uuid.uuid4().hex}",
                "model": json.loads(body_bytes.decode("utf-8")).get("model"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": max(1, len(prompt) // 4),
                    "completion_tokens": max(1, len(text) // 4),
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
            return 200, json.dumps(mock_resp).encode("utf-8")

        def _forward_serial(self, prompt: str, *, purpose: str | None = None) -> str:
            self.settle_trailing_pending("eoh_skipped")
            self.last_request_index = None
            if purpose is not None and purpose not in {"eoh_probe", "eoh_generation", "eoh_repair"}:
                raise ValueError("gateway_purpose_denied")
            if self.terminal:
                raise BudgetExhausted(self.last_error or "provider_terminal")
            remaining = self._remaining_wall()
            if remaining is not None and remaining <= 0:
                self.last_error = "wall_time_exhausted"
                self.terminal = True
                raise BudgetExhausted("wall_time_exhausted")
            if purpose is None:
                purpose = "eoh_probe" if prompt.strip() == "1+1=?" else "eoh_generation"
            if purpose == "eoh_repair" and self.repair_limit is not None and self.repair_used >= self.repair_limit:
                raise BudgetExhausted("repair_request_limit")

            if self._ledger_path is not None and (self._routing_policy.enabled or self._strict_barriers):
                route = allocate_logical_route(
                    self._ledger_path,
                    run_id=self._run_id,
                    purpose=purpose,
                    policy=self._routing_policy,
                    created_at_utc=_utc_now(),
                )
            else:
                route = {
                    "logical_call_id": f"lcall_{uuid.uuid4().hex}",
                    "logical_ordinal": None,
                    "requested_model": self.model,
                    "route_role": "single_model",
                }

            backoff_schedule = (5.0, 15.0, 30.0) if not self._use_mock else (0.01, 0.01)
            last_exc: Exception | None = None
            for retry_idx in range(len(backoff_schedule) + 1):
                rem_wall = self._remaining_wall()
                if rem_wall is not None and rem_wall <= 0:
                    self.last_error = "wall_time_exhausted"
                    self.terminal = True
                    raise BudgetExhausted("wall_time_exhausted")

                chosen_model = str(route["requested_model"])
                payload: dict[str, Any] = {
                    "model": chosen_model,
                    "messages": [{"role": "user", "content": prompt}],
                    **generation_parameters(self.target_url, self.thinking, repair=purpose == "eoh_repair"),
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "eoh-frozen-bridge/0908",
                    "X-Request-Purpose": purpose,
                }
                if self._opencode:
                    headers["x-opencode-session"] = self.session_id

                slot = self.budget.reserve(
                    purpose=purpose,
                    problem=self.problem,
                    attempt=retry_idx + 1,
                    model=chosen_model,
                    logical_call_id=route["logical_call_id"],
                    logical_ordinal=route["logical_ordinal"],
                    retry_index=retry_idx,
                    requested_model=chosen_model,
                )
                if slot is None and self.budget.denial_reason == "checkpoint_pending" and self._ledger_path is not None:
                    self.settle_trailing_pending("eoh_skipped")
                    slot = self.budget.reserve(
                        purpose=purpose,
                        problem=self.problem,
                        attempt=retry_idx + 1,
                        model=chosen_model,
                        logical_call_id=route["logical_call_id"],
                        logical_ordinal=route["logical_ordinal"],
                        retry_index=retry_idx,
                        requested_model=chosen_model,
                    )
                if slot is None:
                    self.last_error = getattr(self.budget, "denial_reason", None) or "request_budget_exhausted"
                    self.terminal = True
                    raise BudgetExhausted(self.last_error)

                self.last_request_index = slot.index
                self._log_event(slot.reserved_event)
                if purpose == "eoh_repair":
                    self.repair_used += 1
                started = time.monotonic()
                req_timeout = self.timeout if rem_wall is None else min(self.timeout, max(0.05, rem_wall))

                try:
                    if self.request_log is not None:
                        _atomic_write_text(
                            self.request_log.parent / "request_inputs" / f"request_{slot.index}.json",
                            json.dumps(payload, ensure_ascii=False),
                        )
                    self.budget.mark_sent(slot)
                    status, raw = self._perform_post(
                        self.target_url, headers, json.dumps(payload).encode("utf-8"), req_timeout, slot=slot, prompt=prompt,
                    )
                    parsed = json.loads(raw.decode("utf-8"))
                    if not isinstance(parsed, dict):
                        raise ValueError("invalid_completion_object")
                    choices = parsed.get("choices") or []
                    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or not isinstance(choices[0].get("message"), dict):
                        raise ValueError("invalid_completion_choices")
                    if not isinstance(parsed.get("usage", {}), dict):
                        raise ValueError("invalid_completion_usage")
                except BudgetExhausted:
                    raise
                except ProviderFailure as exc:
                    last_exc = exc
                    elapsed = time.monotonic() - started
                    if exc.error_code == "request_deadline":
                        self._record(slot, "killed_unknown", error_code="request_deadline", elapsed_seconds=elapsed, requested_model=chosen_model)
                    elif exc.error_code in {"provider_auth_invalid"} or str(exc.error_code).startswith("http_"):
                        self._record(slot, "http_error", status=exc.status, error_code=exc.error_code, elapsed_seconds=elapsed, requested_model=chosen_model)
                    else:
                        self._record(slot, "connectivity_failed", error_code=exc.error_code, elapsed_seconds=elapsed, requested_model=chosen_model)
                    if self._strict_barriers and self._ledger_path is not None and slot.attempt_token:
                        settle_attempt_provenance(self._ledger_path, attempt_token=slot.attempt_token, generation_status="provider_failed")
                        try_seal_draining_checkpoints(self._ledger_path, self._run_id, wall_elapsed_seconds=time.monotonic() - self._run_started)
                    self.last_error = exc.error_code
                    transient = (
                        exc.error_code in {"provider_connectivity_or_protocol_error", "request_deadline"}
                        or exc.status == 429
                        or (isinstance(exc.status, int) and 500 <= exc.status < 600)
                    )
                    if transient and retry_idx < len(backoff_schedule):
                        rem_after = self._remaining_wall()
                        if rem_after is None or rem_after > backoff_schedule[retry_idx]:
                            time.sleep(backoff_schedule[retry_idx])
                            continue
                    self.terminal = True
                    raise
                except Exception as exc:
                    self._record(
                        slot,
                        "connectivity_failed",
                        error_code="provider_connectivity_or_protocol_error",
                        elapsed_seconds=time.monotonic() - started,
                        requested_model=chosen_model,
                    )
                    if self._strict_barriers and self._ledger_path is not None and slot.attempt_token:
                        settle_attempt_provenance(self._ledger_path, attempt_token=slot.attempt_token, generation_status="provider_failed")
                        try_seal_draining_checkpoints(self._ledger_path, self._run_id, wall_elapsed_seconds=time.monotonic() - self._run_started)
                    self.last_error = "provider_connectivity_or_protocol_error"
                    self.terminal = True
                    raise ProviderFailure(self.last_error) from exc

                choices = parsed.get("choices") or []
                message = choices[0].get("message", {}) if choices else {}
                content = message.get("content") if isinstance(message, dict) else None
                reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
                finish_reason = choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None
                usage_fields = extract_provider_usage(parsed)
                cost_usd, priced, _ = compute_attempt_cost_usd(
                    model_alias=chosen_model,
                    input_tokens=usage_fields["input_tokens"],
                    output_tokens=usage_fields["output_tokens"],
                    cached_tokens=usage_fields["cached_tokens"],
                    rate_card=self._routing_policy.rate_card,
                )
                elapsed = time.monotonic() - started
                response_metadata = {
                    "request_payload": payload,
                    "requested_model": chosen_model,
                    "served_model": usage_fields["served_model"],
                    "provider_request_id": usage_fields["provider_request_id"],
                    "logical_call_id": route["logical_call_id"],
                    "logical_ordinal": route["logical_ordinal"],
                    "retry_index": retry_idx,
                    "finish_reason": finish_reason,
                    "content_present": isinstance(content, str) and bool(content.strip()),
                    "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning.strip()),
                    "selected_content_field": "content" if isinstance(content, str) and content.strip() and finish_reason != "length" else None,
                    "response_policy": "content_only_complete_v1",
                    "raw_response": parsed,
                    "usage": parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {},
                    "cached_tokens": usage_fields["cached_tokens"],
                    "rate_card_version": self._routing_policy.rate_card_version,
                    "estimated_cost_usd": cost_usd if priced else None,
                }
                self.last_completion = parsed
                bad_content = finish_reason == "length" or not isinstance(content, str) or not content.strip()
                if bad_content:
                    err = "generation_truncated" if finish_reason == "length" else "empty_or_nontext_completion"
                    response_metadata["response_error"] = err
                    self._save_exchange(slot, prompt, content if isinstance(content, str) else "", metadata=response_metadata)
                    self._record(
                        slot,
                        "complete",
                        status=status,
                        error_code=err,
                        elapsed_seconds=elapsed,
                        input_tokens=usage_fields["input_tokens"],
                        output_tokens=usage_fields["output_tokens"],
                        cached_tokens=usage_fields["cached_tokens"],
                        finish_reason=finish_reason,
                        selected_content_field=None,
                        requested_model=chosen_model,
                        served_model=usage_fields["served_model"],
                        provider_request_id=usage_fields["provider_request_id"],
                        rate_card_version=self._routing_policy.rate_card_version,
                        estimated_cost_usd=cost_usd if priced else None,
                    )
                    if self._strict_barriers and self._ledger_path is not None and slot.attempt_token:
                        settle_attempt_provenance(self._ledger_path, attempt_token=slot.attempt_token, generation_status="malformed_response")
                        try_seal_draining_checkpoints(self._ledger_path, self._run_id, wall_elapsed_seconds=time.monotonic() - self._run_started)
                    self.last_error = err
                    raise ValueError(err)

                self._save_exchange(slot, prompt, content, metadata=response_metadata)
                self._record(
                    slot,
                    "complete",
                    status=status,
                    error_code=None,
                    elapsed_seconds=elapsed,
                    input_tokens=usage_fields["input_tokens"],
                    output_tokens=usage_fields["output_tokens"],
                    cached_tokens=usage_fields["cached_tokens"],
                    finish_reason=finish_reason,
                    selected_content_field="content",
                    requested_model=chosen_model,
                    served_model=usage_fields["served_model"],
                    provider_request_id=usage_fields["provider_request_id"],
                    rate_card_version=self._routing_policy.rate_card_version,
                    estimated_cost_usd=cost_usd if priced else None,
                )
                if self._strict_barriers and self._ledger_path is not None and slot.attempt_token:
                    if purpose == "eoh_probe":
                        settle_attempt_provenance(self._ledger_path, attempt_token=slot.attempt_token, generation_status="probe")
                        try_seal_draining_checkpoints(self._ledger_path, self._run_id, wall_elapsed_seconds=time.monotonic() - self._run_started)
                    else:
                        with self._token_lock:
                            self._pending_attempt_token = slot.attempt_token
                self.last_error = None
                return content

            assert last_exc is not None
            raise last_exc

    return _RoutedSessionBridge()


def execute_m2_session_task(
    *,
    root: Path,
    task_id: str,
    row: Mapping[str, Any],
    rd: Mapping[str, Any],
    config: Mapping[str, Any],
    plan: Mapping[str, Any],
    design: InterfaceDesign,
    suite: Mapping[str, Any],
    output: Path,
    wall_seconds: float,
    policy: Mapping[str, int],
    parent_skill_path: str | None,
    seed_selection_path: str | None,
    previous_design: InterfaceDesign | None,
) -> None:
    """Execute one Session round using validated dynamic interface inside Session authority."""
    from eoh import LLMConfig
    from eoh.config import EoHConfig
    from agent_skill_loop.client import ProviderFailure, load_local_env

    t_run0 = time.monotonic()
    tpl = get_template_spec(design.template_id, design.template_version)
    adapter = resolve_problem_adapter(tpl, problem_family=design.problem_family, protocol_id=design.protocol_id)

    output.mkdir(parents=True, exist_ok=True)
    results_dir = output / "results"
    for sub in ("samples", "pops", "pops_best", "evaluation_starts", "exchanges"):
        (results_dir / sub).mkdir(parents=True, exist_ok=True)

    eval_log = results_dir / "evaluations.jsonl"
    req_log = results_dir / "requests.jsonl"
    instances = _normalize_session_suite_instances(suite, problem_family=design.problem_family)
    suite_hash = str(row["suite_hash"])
    eval_hash = str(row["evaluator_hash"])
    metric_hash = row["metric_spec_hash"] if "metric_spec_hash" in row.keys() else None
    problem_spec_hash = row["problem_spec_hash"] if "problem_spec_hash" in row.keys() else None
    data_manifest_hash = row["data_manifest_hash"] if "data_manifest_hash" in row.keys() else None
    session_ref = {"root": str(root), "task_id": task_id}

    round_context_text = (root / rd["round_context_ref"]).read_text(encoding="utf-8") if rd["round_context_ref"] else ""
    agent_guidance_on = bool(row["agent_guidance"]) if "agent_guidance" in row.keys() else True
    opt_clues = design.template_options.get("inject_static_kb_clues")
    cfg_clues = config.get("inject_static_kb_clues") if isinstance(config, Mapping) else None
    inject_static_kb_clues = (
        bool(opt_clues) if opt_clues is not None else (bool(cfg_clues) if cfg_clues is not None else agent_guidance_on)
    )
    kb_clue = KB_ROUND_CONTEXT_BY_TEMPLATE.get(design.template_id, "") if inject_static_kb_clues else ""
    combined_ctx = (round_context_text + "\n\n" + kb_clue).strip() if kb_clue else round_context_text

    budget_ms = resolve_session_time_budget_ms(plan.get("interface_selection"), config, design)
    options = design.template_options
    no_jump_limit = _early_stop_limit(options)
    extended_numpy = options.get("allow_extended_numpy_whitelist", True)
    fresh_template = (plan.get("interface_selection") or {}).get("fresh_template") is True
    if fresh_template:
        parent_skill_path = seed_selection_path = None
    kb_release_id, kb_manifest_sha256 = resolve_session_kb_release(config, session_root=root)
    effective_cand_timeout = derive_effective_batch_timeout_s(
        len(instances), budget_ms, floor_s=float(row["solver_timeout"]),
    )

    pb_cfg = config.get("persistent_budget") if isinstance(config, Mapping) else None
    ledger_path = Path(str(pb_cfg["ledger_path"])) if isinstance(pb_cfg, Mapping) and pb_cfg.get("ledger_path") else None
    milestone_run_id = str(pb_cfg.get("run_id") or row["run_id"]) if isinstance(pb_cfg, Mapping) else str(row["run_id"])
    strict_barriers = bool(pb_cfg.get("strict_checkpoint_barriers", False)) if isinstance(pb_cfg, Mapping) else False
    base_owner_epoch = str(pb_cfg.get("owner_epoch") or "") if isinstance(pb_cfg, Mapping) and pb_cfg.get("owner_epoch") else None
    owner_epoch = f"{base_owner_epoch}:{task_id}" if base_owner_epoch else f"task:{task_id}"
    wall_offset_s = get_run_wall_offset_seconds(ledger_path, milestone_run_id) if ledger_path is not None else 0.0
    t_wall_origin = t_run0 - wall_offset_s
    routing_policy = ModelRoutingPolicy.from_dict(config.get("model_routing") if isinstance(config, Mapping) else None)
    if not routing_policy.enabled:
        routing_policy = ModelRoutingPolicy(
            enabled=False,
            weak_model=str(row["eoh_model"]),
            strong_model=str(row["eoh_model"]),
            rate_card=routing_policy.rate_card,
            rate_card_version=routing_policy.rate_card_version,
        )

    endpoint = str(row["eoh_endpoint"])
    model = str(row["eoh_model"])
    api_key_env = str(row["eoh_api_key_env"])
    request_timeout = float(row["request_timeout"])
    use_mock = endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"

    parent_budget = None
    if ledger_path is not None:
        from agent_skill_loop.request_budget import PersistentRequestBudget

        parent_budget = PersistentRequestBudget(
            ledger_path,
            pb_cfg.get("max_requests") if isinstance(pb_cfg, Mapping) else None,
            run_id=milestone_run_id,
            reconcile_inflight=False,
            strict_checkpoint_barriers=strict_barriers,
            owner_epoch=owner_epoch,
        )
    budget = SessionRequestBudget(str(root), task_id, parent=parent_budget)

    bridge = None
    mock_srv = None
    use_routed_bridge = (not use_mock) or strict_barriers or routing_policy.enabled
    if use_routed_bridge:
        if not use_mock:
            load_local_env()
            api_key = os.environ.get(api_key_env, "").strip()
            if not api_key:
                summary = {
                    "problem": str(row["problem"]),
                    "status": "provider_failed",
                    "stop_reason": "provider_error",
                    "provider_error_code": f"missing_api_key:{api_key_env}",
                    "loop_completed": False,
                }
                _atomic_write_text(output / "summary.json", json.dumps(summary, indent=2) + "\n")
                return
        else:
            api_key = "mock-key"
        mock_pool = _default_mock_candidates().get(design.template_id, DEFAULT_MOCK_MERGE_CANDIDATES)
        bridge = _build_session_bridge(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            request_timeout=request_timeout,
            budget=budget,
            req_log=req_log,
            wall_seconds=wall_seconds,
            problem=f"{design.template_id}/{design.template_version}",
            routing_policy=routing_policy,
            ledger_path=ledger_path,
            run_id=milestone_run_id,
            strict_barriers=strict_barriers,
            use_mock=use_mock,
            mock_candidates=mock_pool,
            run_started_monotonic=t_wall_origin,
        )
        local_url = bridge.start()
    else:
        mock_pool = _default_mock_candidates().get(design.template_id, DEFAULT_MOCK_MERGE_CANDIDATES)
        mock_srv = MockEoHLLMServer(mock_pool, request_log=req_log)
        local_url = mock_srv.start()

    task = _SessionTrackedDynamicProblem(
        session=session_ref,
        problem_id=str(row["problem"]),
        suite_hash=suite_hash,
        evaluator_hash=eval_hash,
        metric_spec_hash=metric_hash,
        problem_spec_hash=problem_spec_hash,
        data_manifest_hash=data_manifest_hash,
        kb_release_id=kb_release_id,
        milestone_ledger_path=ledger_path,
        milestone_run_id=milestone_run_id,
        strict_checkpoint_barriers=strict_barriers,
        run_started_monotonic=t_wall_origin,
        bridge_ref=bridge,
        design=design,
        instances=instances,
        suite_id=f"session_{row['problem']}",
        distance_convention=str(suite.get("distance_convention") or ("euc_2d_float" if design.problem_family in {"cvrp", "tsp"} else "not_applicable")),
        vehicle_limit_policy=str(suite.get("vehicle_limit_policy") or ("unconstrained" if design.problem_family == "cvrp" else "not_applicable")),
        candidate_timeout_s=effective_cand_timeout,
        instance_time_budget_ms=budget_ms,
        allow_extended_numpy_whitelist=extended_numpy,
        enable_n200_latency_screen=options.get("enable_n200_latency_screen", False),
        enable_degenerate_constant_screen=options.get("enable_degenerate_constant_screen", False),
        n200_latency_multiplier=options.get("n200_latency_multiplier", 1.0),
        evaluation_log=eval_log,
        round_context=combined_ctx,
    )
    _atomic_write_text(output / "task_description.txt", task.task_description)

    baseline_code = tpl.default_template_program if len(tpl.effective_hook_specs) > 1 else design.baseline_hook_code
    baseline_sha = sha256_text(baseline_code)
    seed_origin_by_hash = {baseline_sha: "baseline", design.baseline_hook_sha256: "baseline"}
    seed_entries = [{"algorithm": f"Baseline hook for {design.template_id}/{design.template_version}.",
                     "code": baseline_code}]
    inherited = []
    if seed_selection_path:
        seed_doc = json.loads(Path(seed_selection_path).read_text(encoding="utf-8"))
        inherited = [(m["code"], m["code_sha256"], "population_seed") for m in seed_doc["selected_members"]]
    elif parent_skill_path:
        parent = load_skill(Path(parent_skill_path))
        inherited = [(parent.code, parent.code_sha256, "explicit_parent")]
    for code, checksum, origin in inherited:
        if sha256_text(code) != checksum:
            raise ValueError("interface_seed_code_hash_mismatch")
        if checksum in seed_origin_by_hash:
            continue
        if seed_selection_path and previous_design is not None and (
            previous_design.template_id, previous_design.template_version
        ) != (design.template_id, design.template_version):
            continue
        if len(tpl.effective_hook_specs) > 1:
            try:
                parse_hook_candidate(
                    tpl.template_id, tpl.template_version, code, allow_extended_numpy_whitelist=extended_numpy,
                )
            except (ValueError, SyntaxError):
                continue
        else:
            g1, g2 = validate_hook_ast(
                code, hook_name=tpl.hook_name, expected_args=tpl.hook_signature,
                allow_extended_numpy_whitelist=extended_numpy,
            )
            if g1 or g2:
                continue
        seed_origin_by_hash[checksum] = origin
        seed_entries.append({"algorithm": f"Inherited {origin} ({checksum[:12]}).", "code": code})
    _atomic_write_text(output / "interface_seed_receipt.json", json.dumps({
        "requested_inherited_seeds": len(inherited),
        "used_inherited_seeds": len(seed_entries) - 1,
        "skipped_inherited_seeds": len(inherited) - len(seed_entries) + 1,
        "previous_design_sha256": previous_design.design_sha256 if previous_design is not None else None,
        "reason": "fresh_template" if fresh_template else (
            "no_compatible_seed_restarted_from_template" if inherited and len(seed_entries) == 1 else None
        ),
        "seed_origins": seed_origin_by_hash,
    }, indent=2) + "\n")
    task.seed_origins = seed_origin_by_hash
    baseline_resp = task.evaluate_detailed(baseline_code)
    if not baseline_resp.get("valid"):
        if bridge is not None:
            bridge.stop()
        if mock_srv is not None:
            mock_srv.stop()
        raise ValueError(f"interface_baseline_infeasible:{baseline_resp.get('error_code')}")

    seed_path = output / "seeds" / "baseline_seed.json"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(
        json.dumps(seed_entries[1:] or seed_entries, indent=2) + "\n",
        encoding="utf-8",
    )

    status = "completed"
    stop_reason = "eoh_completed"
    loop_completed = True
    provider_error_code = None
    try:
        llm_cfg = LLMConfig(use_local=True, local_url=local_url, timeout=int(request_timeout) + 5)
        engine_cfg = EoHConfig(
            llm=llm_cfg,
            pop_size=int(policy["pop_size"]),
            n_pop=int(policy["n_pop"]),
            operators=["e1", "e2", "m1", "m2"],
            max_sample_nums=int(policy["max_sample_nums"]),
            num_samplers=1,
            num_evaluators=1,
            use_seed=True,
            seed_path=str(seed_path),
            output_dir=str(output),
        )
        if no_jump_limit:
            engine = _StagnationAwareEoH(engine_cfg, task, evaluation_log=eval_log, no_jump_limit=no_jump_limit)
        else:
            engine = _DynamicCandidateEoH(engine_cfg, task)
        base_seed = int(config.get("search_seed", config["suite_generation"]["seed"]))
        s_seed = base_seed + int(rd["round_id"]) - 1
        random.seed(s_seed)
        np.random.seed(s_seed % (2**32))
        engine.run()
    except StagnationEarlyStop:
        status = "stopped"
        stop_reason = "stagnation_early_stop"
    except Exception as exc:
        msg = str(exc)
        bridge_err = getattr(bridge, "last_error", None) if bridge is not None else None
        bridge_term = bool(getattr(bridge, "terminal", False)) if bridge is not None else False
        is_provider_err = (
            isinstance(exc, ProviderFailure)
            or (
                bridge_term
                and bridge_err is not None
                and bridge_err not in {"request_budget_exhausted", "wall_time_exhausted", "checkpoint_pending", "repair_request_limit", "budget_exhausted"}
            )
        )
        if is_provider_err:
            status = "provider_failed"
            provider_error_code = str(getattr(exc, "error_code", None) or bridge_err or "provider_error")
            stop_reason = provider_error_code
            loop_completed = False
        elif "wall_time_exhausted" in msg or bridge_err == "wall_time_exhausted":
            status = "stopped"
            stop_reason = "wall_time_limit"
        elif "budget_exhausted" in msg or "request_limit" in msg or "checkpoint_pending" in msg:
            status = "stopped"
            stop_reason = "request_limit"
        else:
            status = "engine_failed"
            stop_reason = "engine_error"
            loop_completed = False
    finally:
        if bridge is not None:
            bridge.settle_trailing_pending("eoh_skipped")
            bridge.stop()
        if mock_srv is not None:
            mock_srv.stop()

    rows = [json.loads(line) for line in eval_log.read_text(encoding="utf-8").splitlines() if line.strip()] if eval_log.is_file() else []
    gen_valid = [
        r for r in rows
        if r.get("origin") == "generated"
        and isinstance(r.get("evaluation"), dict)
        and r["evaluation"].get("valid") is True
        and r["evaluation"].get("objective") is not None
    ]
    best_rel = None
    frozen_rel = None
    validator = InterfaceValidator(
        candidate_timeout_s=effective_cand_timeout,
        instance_time_budget_ms=budget_ms,
        outer_timeout_s=effective_cand_timeout,
    )
    validated = []
    best = None
    for candidate in sorted(gen_valid, key=lambda r: float(r["evaluation"]["objective"])):
        if any(r["code_sha256"] == candidate["code_sha256"] for r in validated):
            continue
        try:
            win_primary, win_impls = task._resolve_hook_payload(str(candidate["code"]))
        except (ValueError, SyntaxError):
            continue
        report = validator.validate(
            design,
            hook_code_override=win_primary,
            hook_implementations=win_impls,
        )
        validated.append({"code_sha256": candidate["code_sha256"], "validation": report.as_dict()})
        if report.passed:
            best = (candidate, win_primary, win_impls)
            break
    _atomic_write_text(output / "winner_validation_report.json", json.dumps(validated, indent=2) + "\n")
    if best is not None:
        best_rec, win_primary, win_impls = best
        ev = best_rec["evaluation"]
        skill_dir = output / "skills" / "best_generated"
        sv = SkillVersion(
            version_id=f"m2_r{rd['round_id']:04d}_{best_rec['code_sha256'][:10]}",
            problem=str(row["problem"]),
            entrypoint=design.hook_name,
            code=str(best_rec["code"]),
            code_sha256=str(best_rec["code_sha256"]),
            parent_version_id=None,
            suite_hash=suite_hash,
            evaluator_hash=eval_hash,
            valid=True,
            mean_objective=float(ev["objective"]),
            instance_objectives=tuple(float(x) for x in ev.get("instance_objectives") or ()),
            source_attempt_id=None,
            description=f"Session M2 evolved {design.template_id}/{design.template_version}:{design.hook_name}",
            search_policy_id="official_eoh",
            search_policy_version=EOH_COMMIT,
            origin="generated",
            metric_spec_hash=metric_hash,
        )
        save_skill(skill_dir, sv)
        best_rel = "skills/best_generated"

        primary_src = win_primary or str(best_rec["code"])
        frozen = FrozenInterfaceSolver(
            solver_id=f"session_r{rd['round_id']:04d}_{design.template_id}_{best_rec['code_sha256'][:8]}",
            display_name=f"Session R{rd['round_id']} · {design.template_id}",
            problem_family=design.problem_family,
            paradigm=design.paradigm,
            template_id=design.template_id,
            template_version=design.template_version,
            template_source_sha256=tpl.template_source_sha256,
            postprocess_mode=design.postprocess_mode,
            template_options=dict(design.template_options),
            hook_name=design.hook_name,
            hook_code=primary_src,
            hook_code_sha256=sha256_text(primary_src),
            design_sha256=design.design_sha256,
            origin_run=str(output),
            kb_release_id=kb_release_id,
            kb_entry_id=design.cited_kb_ids[0] if design.cited_kb_ids else None,
            cited_kb_ids=design.cited_kb_ids,
            diagnostic_ref=design.diagnostic_ref,
            description=sv.description,
            default_budget_ms=budget_ms,
            protocol_id=adapter.protocol_id,
            hook_specs=tpl.hook_specs,
            hook_implementations=win_impls or {},
        )
        _atomic_write_text(
            output / "frozen_solver_manifest.json",
            json.dumps(frozen.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
        frozen_rel = "frozen_solver_manifest.json"

    summary = {
        "problem": str(row["problem"]),
        "problem_family": design.problem_family,
        "protocol_id": adapter.protocol_id,
        "search": "official_eoh",
        "interface_mode": "m2_dynamic_interface",
        "template_id": design.template_id,
        "template_version": design.template_version,
        "template_source_sha256": tpl.template_source_sha256,
        "design_sha256": design.design_sha256,
        "instance_time_budget_ms": budget_ms,
        "effective_candidate_timeout_s": effective_cand_timeout,
        "kb_release_id": kb_release_id,
        "kb_manifest_sha256": kb_manifest_sha256,
        "static_kb_clues_injected": inject_static_kb_clues,
        "task_description_sha256": sha256_text(task.task_description),
        "eoh_commit": EOH_COMMIT,
        "suite_hash": suite_hash,
        "evaluator_hash": eval_hash,
        "status": status,
        "stop_reason": stop_reason,
        "provider_error_code": provider_error_code,
        "loop_completed": loop_completed,
        "baseline": baseline_resp.get("objective"),
        "best_generated_path": best_rel,
        "exported_skill": best_rel,
        "frozen_solver_manifest": frozen_rel,
    }
    _atomic_write_text(output / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
