"""Main crash-recoverable autonomous Research Agent loop orchestrating Session Runtime."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.model_routing import ModelRoutingPolicy
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver, resolve_problem_adapter
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.session_bridge import _summarize_records_for_checkpoint
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.milestone_checkpoint import (
    export_sealed_checkpoints,
    initialize_milestone_schedule,
    price_ledger_records_with_rate_card,
    read_milestone_status,
    set_run_wall_offset_seconds,
    settle_pending_provenance_for_terminal_requests,
    try_seal_draining_checkpoints,
)
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import (
    STAGNATION_DIAGNOSTIC_TOOLS,
    AgentCheckpoint,
    AgentConfig,
    append_results_tsv_row,
    atomic_write_json,
    atomic_write_text,
    sha256_text,
    utc_now,
)
from research_agent.llm_driver import AgentDriver, OpenAIAgentDriver, ScriptedMockAgentDriver
from research_agent.prompts import RESEARCH_POLICY_MD, build_round_observation_message
from research_agent.tools.archive_tools import SteppingStoneArchiveTool
from research_agent.tools.diagnostic_tools import DiagnosticTool
from research_agent.tools.interface_tools import InterfaceTool
from research_agent.tools.kb_tools import KnowledgeBaseTool
from research_agent.tools.ledger_tools import HypothesisLedgerTool
from research_agent.tools.math_sandbox import (
    SANDBOX_REF_KEYS,
    MathSandboxTool,
    _has_finite_numeric_evidence,
)
from research_agent.tools.session_tools import SessionRunnerTool


def _resolve_latest_evidence_refs(
    raw_refs: list[dict[str, Any]],
    *,
    last_sandbox: dict[str, Any] | None,
    last_diag: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in raw_refs:
        if item.get("use_latest_sandbox") and last_sandbox:
            resolved.append({
                "path": last_sandbox["artifact_ref"],
                "sha256": last_sandbox["artifact_sha256"],
                "kind": "sandbox",
            })
            resolved.append({
                "path": last_sandbox["script_ref"],
                "sha256": last_sandbox["script_sha256"],
                "kind": "sandbox_script",
            })
        elif item.get("use_latest_diag") and last_diag:
            resolved.append({
                "path": last_diag["artifact_ref"],
                "sha256": last_diag["artifact_sha256"],
                "kind": "diagnostic",
            })
        else:
            resolved.append(dict(item))
    return resolved


def _round_inner_requests(session_out: Mapping[str, Any], fallback_used: int) -> int:
    """Return inner Session requests used without treating an initial 0 as missing."""
    req_after = session_out.get("requests_after")
    req_before = session_out.get("requests_before")
    after_val = int(req_after) if req_after is not None else int(fallback_used)
    before_val = int(req_before) if req_before is not None else int(fallback_used)
    return max(0, after_val - before_val)


_SESSION_TERMINATION_FIELDS = ("session_status", "completion_reason", "stop_reason", "termination_reason", "terminal_reason")
_SESSION_TRAJECTORY_FIELDS = ("fresh_template_applied", "stagnation_trigger_ordinal")
# A live controller call can use its initial attempt and three provider retries.
_CONTROLLER_ATTEMPT_LIMIT = 4
_SESSION_BUDGET_REASONS = frozenset({
    "budget_exhausted", "request_budget_exhausted", "eoh_request_budget_exhausted",
    "eoh_round_request_budget_exhausted", "solver_budget_exhausted", "phase_budget_exhausted",
    "deadline_exceeded", "wall_budget_exhausted", "wall_time_exhausted", "engine_wall_budget_exhausted",
})


def _session_terminal_phase(outcome: Mapping[str, Any]) -> str | None:
    status = outcome.get("session_status")
    if status == "STOPPED" or any(
        str(outcome.get(key) or "").casefold() in _SESSION_BUDGET_REASONS
        for key in _SESSION_TERMINATION_FIELDS[1:]
    ):
        return "budget_stopped"
    return "completed" if status == "COMPLETED" else None


def _extract_eval_objective(eval_obj: Mapping[str, Any] | None) -> float | None:
    if not isinstance(eval_obj, Mapping):
        return None
    for key in (
        "penalized_mean_objective",
        "penalized_mean_tour_length",
        "mean_objective",
        "mean_tour_length",
    ):
        val = eval_obj.get(key)
        if not isinstance(val, bool) and isinstance(val, (int, float)) and math.isfinite(val):
            return float(val)
    return None


def evaluate_global_stopping_decision(
    config: AgentConfig,
    *,
    t: int,
    candidate_provenance: Sequence[Mapping[str, Any]],
    restart_eligible_round_id: int | None = None,
    pending_restart: bool = False,
    last_restart_ordinal: int | None = None,
) -> dict[str, Any]:
    """Apply the run-level stopping policy to an ordinal prefix of the ledger."""
    mode = config.global_early_stop_mode
    H = config.total_request_cap
    h = max(0, H - t)
    cooldown_met = t - (0 if last_restart_ordinal is None else last_restart_ordinal) >= config.risk_stop_cooldown
    P_t = int(restart_eligible_round_id is not None or pending_restart or not cooldown_met)
    incumbent = None
    incumbent_ordinal = None
    non_improving = 0
    excluded_non_candidate_attempts = 0
    attempts: list[bool] = []
    jump_rel_gains: list[float] = []
    for row in sorted(candidate_provenance, key=lambda row: row["global_ordinal"]):
        ordinal = row["global_ordinal"]
        status = row["generation_status"]
        if ordinal > t or status in {"pending", "probe", "eoh_probe"} or row.get("purpose") == "eoh_probe":
            continue
        key = None
        objective = row.get("dev_penalized_mean")
        if row.get("eligible") and objective is not None and math.isfinite(objective):
            key = (bool(row["dev_all_feasible"]), float(row["dev_completion_rate"]), -objective, -ordinal)
        improved = key is not None and (incumbent is None or key > incumbent)
        if improved:
            if (
                incumbent is not None and incumbent[0] and incumbent[1] >= 1.0 - 1e-12
                and key[0] and key[1] >= 1.0 - 1e-12
                and key[2] > incumbent[2] and incumbent[2] != 0
            ):
                jump_rel_gains.append((key[2] - incumbent[2]) / abs(incumbent[2]))
            incumbent = key
            incumbent_ordinal = ordinal
        if status in {"valid_candidate", "invalid_candidate"}:
            attempts.append(improved)
            non_improving = 0 if improved else non_improving + 1
        elif status != "baseline_seed":
            excluded_non_candidate_attempts += 1

    top_tier = incumbent is not None and incumbent[0] and incumbent[1] >= 1.0 - 1e-12
    window = attempts[-config.risk_stop_window:]
    jumps = sum(window)
    a_t = config.risk_stop_prior_a + jumps
    b_t = config.risk_stop_prior_b + len(window) - jumps
    # log(1-q) = -sum(log(1 + a/(b+j))). expm1 retains accuracy for small risks.
    q_t = -math.expm1(-math.fsum(math.log1p(a_t / (b_t + j)) for j in range(h)))
    recent_gains = jump_rel_gains[-3:]
    D_t = max(config.risk_stop_d_floor, max(recent_gains, default=0.015))
    expected_regret = D_t * q_t
    tail_bound = min(q_t, expected_regret / 0.10)
    stop = False
    if h > 0 and top_tier and P_t == 0:
        if mode == "naive_patience":
            stop = non_improving >= config.global_early_stop_patience
        elif mode == "risk_bounded_beta_geom":
            stop = (
                len(window) > 0
                and t >= config.risk_stop_min_requests
                and expected_regret <= config.risk_stop_eps
                and tail_bound <= config.risk_stop_alpha
            )
    return {
        "mode": mode, "stop": stop, "t": t, "H": H, "h": h,
        "top_tier": top_tier, "incumbent_ordinal": incumbent_ordinal, "P_t": P_t,
        "restart_eligible_round_id": restart_eligible_round_id, "pending_restart": pending_restart,
        "last_restart_ordinal": last_restart_ordinal, "cooldown_met": cooldown_met,
        "non_improving_attempts": non_improving, "window_attempts": len(window), "window_jumps": jumps,
        "excluded_non_candidate_attempts": excluded_non_candidate_attempts,
        "a_t": a_t, "b_t": b_t, "q_t": q_t, "D_t": D_t,
        "last_3_jump_rel_gains": recent_gains, "expected_regret_bound": expected_regret, "tail_bound": tail_bound,
    }


def _read_stopping_provenance(budget: PersistentRequestBudget, through: int) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(budget.ledger_path)) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT global_ordinal, purpose, generation_status, eligible,
                      dev_all_feasible, dev_completion_rate, dev_penalized_mean
               FROM candidate_provenance
               WHERE run_id=? AND global_ordinal<=? ORDER BY global_ordinal""",
            (budget.run_id, through),
        )]


def _append_tool_result(
    messages: list[dict[str, Any]],
    decision: Mapping[str, Any],
    tool_name: str,
    arguments: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    if decision.get("tool_call_id"):
        call_id = str(decision["tool_call_id"])
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }],
        })
        messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False, default=str)})
    else:
        messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
        messages.append({
            "role": "user",
            "content": json.dumps({"tool": tool_name, "result": result}, ensure_ascii=False, default=str),
        })


def _build_initial_baseline_solver(config: AgentConfig) -> FrozenInterfaceSolver:
    tpl = get_template_spec(config.initial_template_id, config.version_for_template(config.initial_template_id))
    adapter = resolve_problem_adapter(tpl)
    design = build_design_for_template(
        tpl.template_id,
        tpl.template_version,
        design_id=f"baseline_{tpl.template_id}_{tpl.template_version}",
        postprocess_mode=config.initial_postprocess_mode,
        rationale="Ordinal-0 baseline seed for milestone checkpoints.",
    )
    return FrozenInterfaceSolver(
        solver_id=f"{config.run_id}_baseline_0",
        display_name=f"Baseline {tpl.problem_family}:{tpl.template_id}/{tpl.template_version}",
        problem_family=tpl.problem_family,
        paradigm=tpl.paradigm,
        template_id=tpl.template_id,
        template_version=tpl.template_version,
        template_source_sha256=tpl.template_source_sha256,
        postprocess_mode=config.initial_postprocess_mode,
        template_options={"inject_static_kb_clues": config.kb_enabled and config.inject_static_kb_clues},
        hook_name=tpl.hook_name,
        hook_code=tpl.default_baseline_hook_code,
        hook_code_sha256=sha256_text(tpl.default_baseline_hook_code),
        design_sha256=design.design_sha256,
        origin_run=config.run_id,
        kb_release_id="milestone_baseline_0",
        kb_entry_id=None,
        description=f"Verified ordinal-0 baseline for {config.run_id}.",
        default_budget_ms=float(config.instance_time_budget_ms),
        protocol_id=adapter.protocol_id,
        hook_specs=tpl.hook_specs,
        hook_implementations=tpl.baseline_implementations() if tpl.hook_specs else {},
    )


def run_research_agent(
    config: AgentConfig,
    *,
    driver: AgentDriver | None = None,
    session_factory: Callable[..., SessionRunnerTool] | None = None,
    resume: bool = False,
    common_start: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run or crash-resume the autonomous Research Agent across multi-round Session execution."""
    run_dir = Path(config.output_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = run_dir / "agent_config.json"
    ckpt_path = run_dir / "agent_checkpoint.json"
    policy_path = run_dir / "research_policy.md"
    tsv_path = run_dir / "results.tsv"
    fork_path = run_dir / "common_start_sha256.json"
    global_stopping_enabled = config.global_early_stop_mode != "off"

    if not resume and ckpt_path.exists():
        raise FileExistsError(f"research_agent_checkpoint_already_exists:{ckpt_path}")
    if common_start is not None and not (config.strict_checkpoint_barriers and config.use_benchmark_dev_suite):
        raise ValueError("common_start_requires_strict_benchmark_run")
    fork_digest = sha256_text(json.dumps(common_start, sort_keys=True, allow_nan=False)) if common_start is not None else None
    if fork_path.is_file():
        if json.loads(fork_path.read_text(encoding="utf-8")) != fork_digest:
            raise ValueError("resume_common_start_mismatch")
    elif fork_digest is not None:
        if ckpt_path.is_file():
            raise ValueError("resume_common_start_missing")
        atomic_write_json(fork_path, fork_digest)

    if not policy_path.is_file():
        atomic_write_text(policy_path, RESEARCH_POLICY_MD)
    if not cfg_path.is_file():
        atomic_write_json(cfg_path, config.to_dict())
    elif resume:
        persisted_cfg = AgentConfig.from_dict(json.loads(cfg_path.read_text(encoding="utf-8")))
        immutable_fields = (
            "run_id",
            "problem_family",
            "arm_id",
            "mode",
            "endpoint",
            "planner_model",
            "eoh_model",
            "checkpoint_budgets",
            "strict_checkpoint_barriers",
            "model_routing_policy",
            "dev_suite_id",
            "dev_split",
            "use_benchmark_dev_suite",
            "tools_enabled",
            "archive_feedback_enabled",
            "agent_guidance",
            "inject_static_kb_clues",
            "initial_template_id",
            "initial_postprocess_mode",
            "dev_instance_count",
            "dev_instance_size",
            "instance_time_budget_ms",
            "allowed_templates",
            "allowed_postprocess_modes",
            "search_seed",
            "allow_extended_numpy_whitelist",
            "enable_n200_latency_screen",
            "enable_multiscale_latency_ratio_screen",
            "max_n200_n100_ratio",
            "multiscale_ratio_min_t200_ms",
            "multiscale_n200_abs_cap_ms",
            "enable_degenerate_constant_screen",
            "n200_latency_multiplier",
            "enable_stagnation_diagnostic_gate",
            "stagnation_diagnostic_mode",
            "strict_diagnostic_gate",
            "early_stop_no_jump_requests",
            "basin_restart_on_stagnation",
            "template_version",
            "enable_c2_joint_screen",
            "global_early_stop_mode",
            "global_early_stop_patience",
            "risk_stop_window",
            "risk_stop_prior_a",
            "risk_stop_prior_b",
            "risk_stop_eps",
            "risk_stop_alpha",
            "risk_stop_d_floor",
            "risk_stop_min_requests",
            "risk_stop_cooldown",
            "memory_enabled",
            "require_c2_multiscale_admission",
            "memory_online_writeback_enabled",
            "memory_store_path",
            "memory_mode",
            "kb_enabled",
            "pinned_kb_release_id",
            "pinned_kb_manifest_sha256",
            "memory_max_solution_cards",
            "memory_mmr_lambda",
            "memory_cooldown_rounds",
        )
        for field_name in immutable_fields:
            if getattr(persisted_cfg, field_name) != getattr(config, field_name):
                raise ValueError(
                    f"resume_config_mismatch:{field_name}:{getattr(persisted_cfg, field_name)}!={getattr(config, field_name)}"
                )
        if config.pinned_kb_release_id is not None and persisted_cfg.kb_store_path != config.kb_store_path:
            raise ValueError("resume_config_mismatch:kb_store_path")
        if int(config.total_request_cap) > int(persisted_cfg.total_request_cap):
            raise ValueError(
                f"resume_config_mismatch:total_request_cap:{persisted_cfg.total_request_cap}<{config.total_request_cap}"
            )

    if ckpt_path.is_file():
        ckpt = AgentCheckpoint.from_dict(json.loads(ckpt_path.read_text(encoding="utf-8")))
    else:
        ckpt = AgentCheckpoint(
            run_id=config.run_id,
            current_round=1,
            phase="diagnose",
            active_template_id=config.initial_template_id,
            active_postprocess_mode=config.initial_postprocess_mode,
        )

    run_t0 = time.monotonic()
    last_wall_tick = run_t0

    def _freeze_checkpoint(ckpt_budget: int, used_now: int) -> None:
        if config.strict_checkpoint_barriers:
            return
        if ckpt.best_solver_manifest_ref:
            src = run_dir / ckpt.best_solver_manifest_ref
            if src.is_file():
                dst = run_dir / "checkpoints" / f"frozen_checkpoint_{ckpt_budget}.json"
                atomic_write_json(
                    dst,
                    {
                        "checkpoint_budget": int(ckpt_budget),
                        "triggered_at_used": int(used_now),
                        "captured_at": utc_now(),
                        "best_dev_objective": ckpt.best_dev_objective,
                        "frozen_solver": json.loads(src.read_text(encoding="utf-8")),
                    },
                )
                ckpt.frozen_checkpoints[str(ckpt_budget)] = str(dst.relative_to(run_dir).as_posix())

    budget = PersistentRequestBudget(
        run_dir / "agent_budget.sqlite3",
        max_requests=config.total_request_cap,
        run_id=config.run_id,
        checkpoint_budgets=config.checkpoint_budgets,
        on_checkpoint=None if config.strict_checkpoint_barriers else _freeze_checkpoint,
        reconcile_inflight=True,
        strict_checkpoint_barriers=bool(config.strict_checkpoint_barriers),
    )

    kb_tool = KnowledgeBaseTool(
        run_dir,
        kb_store_path=config.kb_store_path,
        enabled=config.kb_enabled,
        pinned_release_id=config.pinned_kb_release_id,
        pinned_manifest_sha256=config.pinned_kb_manifest_sha256,
    )
    diag_tool = DiagnosticTool(run_dir, dev_suite_id=config.dev_suite_id, dev_split=config.dev_split)
    sandbox_tool = MathSandboxTool(run_dir, timeout_s=config.sandbox_timeout_s)
    iface_tool = InterfaceTool(
        run_dir,
        problem_family=config.problem_family,
        allowed_templates=config.allowed_templates,
        allowed_postprocess_modes=config.allowed_postprocess_modes,
        candidate_timeout_s=config.candidate_timeout_s,
        default_time_budget_ms=config.instance_time_budget_ms,
    )
    archive_tool = SteppingStoneArchiveTool(run_dir, dev_suite_id=config.dev_suite_id, dev_split=config.dev_split)
    ledger_tool = HypothesisLedgerTool(run_dir)
    session_tool = (session_factory or SessionRunnerTool)(run_dir=run_dir, config=config, budget=budget)

    if driver is None:
        if config.mode == "mock":
            driver = ScriptedMockAgentDriver(config=config, budget=budget, session_dir=session_tool.session_dir)
        else:
            driver = OpenAIAgentDriver(config=config, budget=budget, session_dir=session_tool.session_dir)

    def _flush_wall_clock() -> float:
        nonlocal last_wall_tick
        now_mono = time.monotonic()
        delta = max(0.0, now_mono - last_wall_tick)
        last_wall_tick = now_mono
        ckpt.accumulated_wall_seconds = round(float(ckpt.accumulated_wall_seconds or 0.0) + delta, 4)
        if config.strict_checkpoint_barriers:
            set_run_wall_offset_seconds(budget.ledger_path, config.run_id, ckpt.accumulated_wall_seconds)
        return float(ckpt.accumulated_wall_seconds)

    def _save_ckpt() -> None:
        _flush_wall_clock()
        atomic_write_json(ckpt_path, ckpt.to_dict())

    def _sync_strict_checkpoints(*, reconcile_orphans: bool = False) -> None:
        if not config.strict_checkpoint_barriers:
            return
        total_wall = _flush_wall_clock()
        if reconcile_orphans:
            budget.reconcile_orphaned_inflight()
        settle_pending_provenance_for_terminal_requests(budget.ledger_path, config.run_id)
        try_seal_draining_checkpoints(
            budget.ledger_path,
            config.run_id,
            wall_elapsed_seconds=total_wall,
        )
        exported = export_sealed_checkpoints(budget.ledger_path, config.run_id, run_dir / "checkpoints")
        for cp_key, abs_path in exported.items():
            ckpt.frozen_checkpoints[cp_key] = str(Path(abs_path).resolve().relative_to(run_dir).as_posix())

    if config.strict_checkpoint_barriers or global_stopping_enabled:
        initialize_schedule = (
            config.strict_checkpoint_barriers
            and not read_milestone_status(budget.ledger_path, config.run_id)["checkpoints"]
        )
        initialize_baseline = global_stopping_enabled and not _read_stopping_provenance(budget, 0)
        if initialize_schedule or initialize_baseline:
            session_tool.ensure_initialized()
            baseline_solver = _build_initial_baseline_solver(config)
            if config.use_benchmark_dev_suite:
                suite_obj = load_dev_or_public_suite(
                    config.dev_suite_id,
                    split=config.dev_split,
                    role="diagnostic_interactive",
                )
                if common_start is not None:
                    baseline_solver = FrozenInterfaceSolver.from_dict(common_start["frozen_solver"])
                if common_start is None or (
                    global_stopping_enabled and not (common_start.get("baseline_dev_eval") or {}).get("records")
                ):
                    base_dev_eval = session_tool._evaluate_frozen_on_dev(baseline_solver.to_dict())
                else:
                    base_dev_eval = dict(common_start["baseline_dev_eval"])
            else:
                suite_obj = json.loads((session_tool.session_dir / "dev_suite.json").read_text(encoding="utf-8"))
                dist_conv = str(suite_obj.get("distance_convention") or "euc_2d_float")
                veh_pol = str(suite_obj.get("vehicle_limit_policy") or "unconstrained")
                outer_s = max(5.0, float(config.instance_time_budget_ms) / 1000.0 + 3.0)
                base_recs = [
                    evaluate_frozen_interface_solver(
                        baseline_solver,
                        inst,
                        distance_convention=dist_conv,
                        vehicle_limit_policy=veh_pol,
                        solve_deadline_ms=config.instance_time_budget_ms,
                        outer_timeout_s=outer_s,
                        protocol_id=baseline_solver.protocol_id,
                    )
                    for inst in suite_obj["instances"]
                ]
                valid_vals = [float(r["tour_length"]) for r in base_recs if r.get("valid") and r.get("tour_length") is not None]
                pen_vals = [
                    float(r["tour_length"]) if (r.get("valid") and r.get("tour_length") is not None) else 100.0
                    for r in base_recs
                ]
                n_b = len(base_recs)
                base_dev_eval = {
                    "valid_count": len(valid_vals),
                    "instance_count": n_b,
                    "completion_rate": round(len(valid_vals) / max(1, n_b), 6),
                    "all_feasible": bool(n_b > 0 and len(valid_vals) == n_b),
                    "valid_only_mean_tour_length": round(sum(valid_vals) / len(valid_vals), 6) if valid_vals else None,
                    "penalized_mean_tour_length": round(sum(pen_vals) / max(1, n_b), 6),
                    "records": base_recs,
                }
            dev_suite_hash = sha256_text(
                json.dumps(suite_obj["instances"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            )
            if common_start is not None and dev_suite_hash != common_start["dev_suite_hash"]:
                raise ValueError("common_start_dev_suite_mismatch")
            if global_stopping_enabled:
                base_dev_eval = _summarize_records_for_checkpoint(
                    suite_obj["instances"], base_dev_eval["records"],
                    dev_suite_hash=dev_suite_hash, solve_budget_ms=config.instance_time_budget_ms,
                )
            initialize_milestone_schedule(
                budget.ledger_path,
                run_id=config.run_id,
                checkpoint_budgets=config.checkpoint_budgets if config.strict_checkpoint_barriers else (),
                baseline_solver=baseline_solver.to_dict(),
                baseline_dev_eval=base_dev_eval,
                dev_suite_hash=dev_suite_hash,
                solve_budget_ms=float(config.instance_time_budget_ms),
                policy_meta={
                    "arm_id": config.arm_id,
                    "problem_family": config.problem_family,
                    "initial_template_id": config.initial_template_id,
                    "instance_time_budget_ms": float(config.instance_time_budget_ms),
                },
            )
        if common_start is not None and ckpt.best_solver_manifest_ref is None:
            baseline_eval = common_start["baseline_dev_eval"]
            baseline_objective = _extract_eval_objective(baseline_eval)
            if baseline_objective is not None and baseline_eval.get("valid_count", 0) > 0:
                baseline_ref = "agent_artifacts/common_start_solver.json"
                atomic_write_json(run_dir / baseline_ref, common_start["frozen_solver"])
                ckpt.best_solver_manifest_ref = baseline_ref
                ckpt.best_dev_objective = baseline_objective
                ckpt.best_all_feasible = bool(baseline_eval["all_feasible"])
                ckpt.best_completion_rate = float(baseline_eval["completion_rate"])
        _sync_strict_checkpoints()

    _save_ckpt()

    last_diag: dict[str, Any] | None = ckpt.last_diag_ref
    prev_best_dev: float | None = ckpt.best_dev_objective
    round_summaries: list[dict[str, Any]] = list(ckpt.round_summaries)
    diagnostic_mode = config.effective_stagnation_diagnostic_mode
    diagnostic_tools = STAGNATION_DIAGNOSTIC_TOOLS[diagnostic_mode]
    strict_diagnostic_gate = config.strict_diagnostic_gate and bool(diagnostic_tools)
    explicit_diagnostic_mode = config.stagnation_diagnostic_mode != "any"
    track_round_stagnation = bool(diagnostic_tools) or explicit_diagnostic_mode or config.basin_restart_on_stagnation
    deterministic_restart = bool(config.basin_restart_on_stagnation and config.early_stop_no_jump_requests)
    is_s1 = config.arm_id.startswith("arm_s1_")
    hide_arm_label = is_s1 or config.arm_id.startswith("arm_s2_")

    def _global_stopping_at(
        round_id: int, boundary: str, *, pending_restart: bool, terminal_phase: str | None,
    ) -> dict[str, Any]:
        settle_pending_provenance_for_terminal_requests(budget.ledger_path, config.run_id)
        t = budget.used
        last_restart_ordinal = next((
            event["request_ordinal"] for event in reversed(ckpt.trajectory_control_events)
            if event["event"] == "basin_restart" and "request_ordinal" in event
        ), None)
        decision = evaluate_global_stopping_decision(
            config,
            t=t,
            candidate_provenance=_read_stopping_provenance(budget, t),
            restart_eligible_round_id=ckpt.restart_eligible_round_id,
            pending_restart=pending_restart,
            last_restart_ordinal=last_restart_ordinal,
        )
        if terminal_phase == "budget_stopped":
            decision["stop"] = False
        path = run_dir / "stopping_decisions.jsonl"
        row = {"round_id": round_id, "boundary": boundary, "session_terminal_phase": terminal_phase, **decision}
        line = json.dumps(row, allow_nan=False) + "\n"
        if not (resume and path.is_file() and path.read_text(encoding="utf-8").endswith(line)):
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return decision

    def _seal_global_champion(decision: Mapping[str, Any]) -> None:
        ordinal = decision["incumbent_ordinal"]
        with closing(sqlite3.connect(budget.ledger_path)) as con:
            row = con.execute(
                """SELECT solver_manifest_json, dev_penalized_mean, dev_completion_rate
                   FROM candidate_provenance
                   WHERE run_id=? AND global_ordinal=? AND eligible=1""",
                (config.run_id, ordinal),
            ).fetchone()
        if row is None or row[0] is None:
            raise RuntimeError(f"global_early_stop_champion_missing:{ordinal}")
        ref = "checkpoints/global_early_stop_champion.json"
        atomic_write_json(run_dir / ref, json.loads(row[0]))
        ckpt.best_solver_manifest_ref = ref
        ckpt.best_dev_objective = float(row[1])
        ckpt.best_completion_rate = float(row[2])
        ckpt.best_all_feasible = True

    def _diagnostic_required(round_id: int) -> bool:
        return (
            bool(diagnostic_tools)
            and not ckpt.round_diagnostic_called
            and (ckpt.consecutive_stagnant_rounds >= 1 or (round_id >= 2 and not ckpt.diagnostic_ever_called))
        )

    def _record_gate_bypass(round_id: int, reason: str) -> None:
        if strict_diagnostic_gate:
            raise RuntimeError(f"strict_diagnostic_gate_bypass:{round_id}:{reason}")
        if any(event["round_id"] == round_id for event in ckpt.gate_bypass_events):
            return
        ckpt.gate_bypass_events.append({
            "round_id": round_id,
            "reason": reason,
            "stagnation_diagnostic_mode": diagnostic_mode,
            "round_diagnostic_blocks": ckpt.round_diagnostic_blocks,
        })
        ckpt.gate_bypass_count = len(ckpt.gate_bypass_events)
        ckpt.trajectory_control_events.append({
            "round_id": round_id,
            "event": (
                "stagnation_diagnostic_bypassed_on_cap" if reason == "outer_step_cap"
                else "stagnation_diagnostic_bypassed_on_submit"
            ),
        })

    def _satisfy_diagnostic_gate(round_id: int, tool_name: str) -> None:
        if strict_diagnostic_gate and _diagnostic_required(round_id):
            ckpt.trajectory_control_events.append({
                "round_id": round_id,
                "event": "strict_diagnostic_round_satisfied",
                "tool": tool_name,
            })
        ckpt.round_diagnostic_called = True
        ckpt.diagnostic_ever_called = True

    def _stop_for_missing_diagnostic(round_id: int, reason: str) -> None:
        ckpt.trajectory_control_events.append({
            "round_id": round_id,
            "event": "strict_diagnostic_gate_stopped",
            "reason": reason,
        })
        ckpt.round_plan_args = None
        ckpt.pending_submit_tool_call = None
        ckpt.phase = "budget_stopped"
        _save_ckpt()

    def _plan_sandbox_evidence() -> dict[str, Any]:
        return {"sandbox_ref": dict(ckpt.last_sandbox_ref)} if ckpt.last_sandbox_ref is not None else {}

    def _trajectory_observation(round_id: int, restart_available: bool) -> dict[str, Any]:
        return {
            "stagnation_diagnostic_mode": diagnostic_mode,
            "diagnostic_required": _diagnostic_required(round_id),
            "recommended_tools": list(diagnostic_tools),
            "consecutive_stagnant_rounds": ckpt.consecutive_stagnant_rounds,
            "fresh_template_available": restart_available,
        }

    def _archive_observation() -> dict[str, Any]:
        summary = archive_tool.summary()
        if hide_arm_label:
            summary["pareto_frontier"] = [
                {key: value for key, value in entry.items() if key != "arm_id"}
                for entry in summary["pareto_frontier"]
            ]
        return summary

    def _dispatch_tool(tool_name: str, args: Mapping[str, Any], round_id: int) -> dict[str, Any]:
        nonlocal last_diag
        if not config.kb_enabled and tool_name in {"kb_search", "kb_read"}:
            raise PermissionError("kb_disabled_in_arm")
        if not config.tools_enabled and tool_name not in {"hypothesis_propose", "hypothesis_update"}:
            raise PermissionError(f"tool_disabled_in_arm:{tool_name}")
        if tool_name == "kb_search":
            return kb_tool.search(query=str(args.get("query", "")), limit=int(args.get("limit", 5)), problem_family=config.problem_family)
        if tool_name == "kb_read":
            return kb_tool.read(entry_id=str(args["entry_id"]))
        if tool_name in {"memory_search", "memory_read"}:
            if not (config.memory_enabled and config.require_c2_multiscale_admission and ckpt.phase == "diagnose"):
                raise PermissionError("planner_memory_tools_unavailable")
            return session_tool.planner_memory(
                tool_name, args, template_id=ckpt.active_template_id,
                postprocess_mode=ckpt.active_postprocess_mode,
            )
        if tool_name == "diagnose_suite":
            max_instances = args.get("max_instances")
            if (is_s1 or strict_diagnostic_gate) and max_instances is not None and (
                type(max_instances) is not int or max_instances < 1
            ):
                raise ValueError("diagnose_suite_max_instances_must_be_positive_integer")
            res = diag_tool.diagnose_suite(
                template_id=str(args.get("template_id") or ckpt.active_template_id),
                template_version=config.version_for_template(str(args.get("template_id") or ckpt.active_template_id)),
                hook_code=args.get("hook_code"),
                postprocess_mode=str(args.get("postprocess_mode") or ckpt.active_postprocess_mode),
                time_budget_ms=float(args.get("time_budget_ms") or config.instance_time_budget_ms),
                max_instances=max_instances,
            )
            if (
                res.get("error") is None
                and res.get("error_code") is None
                and res.get("ok") is not False
            ):
                if tool_name in diagnostic_tools:
                    if strict_diagnostic_gate:
                        analysis = res.get("analysis") or res
                        valid_count = analysis.get("valid_count")
                        if type(valid_count) is not int or valid_count <= 0:
                            return {**res, "error_code": "stagnation_slice_no_valid_evidence"}
                    _satisfy_diagnostic_gate(round_id, tool_name)
                if res.get("artifact_ref") and res.get("artifact_sha256"):
                    ckpt.last_diag_ref = {key: res[key] for key in ("artifact_ref", "artifact_sha256")}
                    last_diag = ckpt.last_diag_ref
            return res
        if tool_name == "run_math_sandbox":
            res = sandbox_tool.run(script=str(args["script"]))
            binding = {key: res[key] for key in SANDBOX_REF_KEYS}
            ckpt.sandbox_run_refs.append(binding)
            verified = (
                res.get("ok") is True
                and _has_finite_numeric_evidence(res.get("result"))
            )
            if config.strict_diagnostic_gate:
                attempt = {
                    "round_id": round_id,
                    "event": "strict_sandbox_attempt",
                    "artifact_ref": binding["artifact_ref"],
                    "has_finite_numeric_evidence": verified,
                }
                if res.get("repair_hint"):
                    attempt["repair_hint"] = res["repair_hint"]
                ckpt.trajectory_control_events.append(attempt)
            if verified:
                ckpt.last_sandbox_ref = binding
                ckpt.sandbox_success_count += 1
            if (
                tool_name in diagnostic_tools and res.get("ok") is True
                and (verified or (diagnostic_mode == "any" and not strict_diagnostic_gate))
            ):
                _satisfy_diagnostic_gate(round_id, tool_name)
            return {**res, "has_finite_numeric_evidence": verified}
        if tool_name == "list_interfaces":
            interfaces = iface_tool.list_interfaces()
            interfaces["templates"] = [
                item for item in interfaces["templates"]
                if item["template_id"] != "cvrp_parallel_merge_static"
                or item["template_version"] == config.template_version
            ]
            return interfaces
        if tool_name == "propose_and_validate_interface":
            return iface_tool.propose_and_validate(
                template_id=str(args["template_id"]),
                template_version=config.version_for_template(str(args["template_id"])),
                postprocess_mode=str(args.get("postprocess_mode", "none")),
                time_budget_ms=float(args.get("time_budget_ms") or config.instance_time_budget_ms),
                diagnostic_ref=args.get("diagnostic_ref"),
                rationale=str(args.get("rationale", "")),
            )
        if tool_name == "archive_summary":
            return _archive_observation()
        if tool_name == "hypothesis_propose":
            return ledger_tool.propose(
                round_id=round_id,
                statement=str(args["statement"]),
                rationale=str(args.get("rationale", "")),
                hypothesis_id=args.get("hypothesis_id"),
            )
        if tool_name == "hypothesis_update":
            refs = _resolve_latest_evidence_refs(
                list(args.get("evidence_artifacts") or []),
                last_sandbox=ckpt.last_sandbox_ref,
                last_diag=last_diag,
            )
            return ledger_tool.update(
                hypothesis_id=str(args["hypothesis_id"] or ""),
                status=str(args["status"]),
                rationale=str(args.get("rationale", "")),
                evidence_artifacts=refs,
                round_id=round_id,
            )
        raise ValueError(f"unknown_tool:{tool_name}")

    while ckpt.current_round <= config.max_rounds:
        if ckpt.phase in {"completed", "budget_stopped", "no_champion", "early_stopped_global"}:
            break
        r_id = ckpt.current_round
        if r_id in ckpt.completed_rounds:
            ckpt.current_round += 1
            ckpt.phase = "diagnose"
            ckpt.round_step_index = 0
            ckpt.round_outer_requests = 0
            ckpt.round_reflect_requests = 0
            ckpt.round_reflection_finished = False
            ckpt.round_inner_requests = 0
            ckpt.round_prev_best_dev = None
            ckpt.round_plan_args = None
            ckpt.round_diagnostic_called = False
            ckpt.round_diagnostic_blocks = 0
            _save_ckpt()
            continue

        strict_required_round = False
        if strict_diagnostic_gate and ckpt.phase == "diagnose":
            strict_required_round = any(
                event["round_id"] == r_id and event["event"] == "strict_diagnostic_round_required"
                for event in ckpt.trajectory_control_events
            )
            if _diagnostic_required(r_id) and not strict_required_round:
                strict_required_round = True
                ckpt.trajectory_control_events.append({
                    "round_id": r_id,
                    "event": "strict_diagnostic_round_required",
                    "stagnation_diagnostic_mode": diagnostic_mode,
                })
                _save_ckpt()

        if budget.remaining is not None and budget.remaining <= 0 and ckpt.phase == "diagnose":
            if strict_required_round and _diagnostic_required(r_id):
                _stop_for_missing_diagnostic(r_id, "request_budget_exhausted")
            else:
                ckpt.phase = "budget_stopped"
                _save_ckpt()
            break

        restart_available = config.basin_restart_on_stagnation and ckpt.restart_eligible_round_id == r_id
        restart_trigger = None
        if deterministic_restart and restart_available:
            restart_trigger = next((
                event for event in reversed(ckpt.trajectory_control_events)
                if event["round_id"] == r_id - 1 and event["event"] == "stagnation_early_stop"
            ), None)
            restart_available = restart_trigger is not None
        trajectory_observation = None
        if track_round_stagnation:
            trajectory_observation = _trajectory_observation(r_id, restart_available)
        previous_round_summary = round_summaries[-1] if round_summaries else None
        if previous_round_summary is not None and hide_arm_label:
            previous_round_summary = {
                key: value for key, value in previous_round_summary.items() if key != "arm_id"
            }
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": build_round_observation_message(
                    round_id=r_id,
                    budget_remaining=budget.remaining,
                    active_template_id=ckpt.active_template_id,
                    active_postprocess_mode=ckpt.active_postprocess_mode,
                    archive_state=_archive_observation() if config.archive_feedback_enabled else None,
                    previous_round_summary=previous_round_summary,
                    open_hypotheses=ledger_tool.list_records(),
                    trajectory_control=trajectory_observation,
                ),
            }
        ]
        last_tool_res: dict[str, Any] | None = None

        # Phase 1: Diagnose & Plan
        if ckpt.phase == "diagnose":
            while ckpt.round_plan_args is None:
                if budget.remaining is not None and budget.remaining <= 0:
                    if strict_required_round and _diagnostic_required(r_id):
                        _stop_for_missing_diagnostic(r_id, "request_budget_exhausted")
                    else:
                        ckpt.phase = "budget_stopped"
                        _save_ckpt()
                    break

                effective_outer_cap = config.outer_requests_per_round_cap
                if strict_required_round:
                    effective_outer_cap = max(effective_outer_cap, 6)
                elif diagnostic_mode == "any":
                    effective_outer_cap += ckpt.round_diagnostic_blocks
                reserve_restart_slot = (
                    restart_trigger is not None and budget.remaining is not None
                    and budget.remaining <= _CONTROLLER_ATTEMPT_LIMIT
                )
                if ckpt.round_outer_requests >= effective_outer_cap or reserve_restart_slot:
                    bypassed_diag = _diagnostic_required(r_id)
                    if strict_diagnostic_gate and bypassed_diag:
                        _stop_for_missing_diagnostic(r_id, "reserve_restart_slot" if reserve_restart_slot else "outer_step_cap")
                        break
                    if bypassed_diag:
                        _record_gate_bypass(r_id, "outer_step_cap")
                    ckpt.round_plan_args = {
                        "template_id": ckpt.active_template_id,
                        "postprocess_mode": ckpt.active_postprocess_mode,
                        "direction": f"Fallback plan for round {r_id} after reaching outer step cap.",
                        "hypothesis": f"Evolve {ckpt.active_template_id} within remaining EoH budget.",
                        "cited_kb_ids": [],
                        "rationale": (
                            "Reserve remaining requests for the basin restart."
                            if reserve_restart_slot else "Outer round cap reached."
                        ),
                        **_plan_sandbox_evidence(),
                        **({"diagnostic_bypassed_on_cap": True} if bypassed_diag else {}),
                    }
                    ckpt.phase = "session_evolve"
                    _save_ckpt()
                    break

                if track_round_stagnation:
                    observation = json.loads(messages[0]["content"])
                    observation["trajectory_control"] = _trajectory_observation(r_id, restart_available)
                    messages[0]["content"] = json.dumps(observation, ensure_ascii=False, indent=2)

                if (
                    ckpt.round_outer_requests == effective_outer_cap - 1
                    and ckpt.round_outer_requests > 0
                    and not _diagnostic_required(r_id)
                ):
                    messages.append({
                        "role": "user",
                        "content": (
                            "FINAL allowed outer step in diagnose phase for this round. "
                            "You MUST call `submit_plan_and_evolve` (or output strict JSON `submit_plan`) NOW."
                        ),
                    })

                try:
                    dec = driver.decide_step(
                        round_id=r_id,
                        phase="diagnose",
                        step_index=ckpt.round_step_index,
                        messages=messages,
                        last_tool_result=last_tool_res,
                    )
                except ProviderFailure:
                    if config.strict_checkpoint_barriers:
                        _sync_strict_checkpoints()
                    _save_ckpt()
                    raise
                if config.strict_checkpoint_barriers:
                    _sync_strict_checkpoints()
                act = str(dec.get("action") or "")
                if act == "call_tool" and dec.get("tool") == "submit_plan_and_evolve":
                    dec = {
                        **dict(dec.get("arguments") or {}),
                        "action": "submit_plan",
                        "tool_call_id": dec.get("tool_call_id"),
                    }
                    act = "submit_plan"
                if act == "budget_exhausted":
                    if (
                        config.strict_checkpoint_barriers
                        and dec.get("denial_reason") == "checkpoint_pending"
                        and (budget.remaining is None or budget.remaining > 0)
                    ):
                        _sync_strict_checkpoints()
                        _save_ckpt()
                        continue
                    if strict_required_round and _diagnostic_required(r_id):
                        _stop_for_missing_diagnostic(r_id, "request_budget_exhausted")
                    else:
                        ckpt.phase = "budget_stopped"
                        _save_ckpt()
                    break
                ckpt.round_outer_requests += 1
                if act == "call_tool":
                    tname = str(dec["tool"])
                    targs = dict(dec.get("arguments") or {})
                    try:
                        tres = _dispatch_tool(tname, targs, r_id)
                    except Exception as exc:
                        tres = {"error": f"{type(exc).__name__}: {exc}"}
                    last_tool_res = tres
                    _append_tool_result(messages, dec, tname, targs, tres)
                    ckpt.round_step_index += 1
                    _save_ckpt()
                    continue
                if act == "submit_plan":
                    diagnostic_required = _diagnostic_required(r_id)
                    if diagnostic_required and (strict_diagnostic_gate or ckpt.round_diagnostic_blocks < 2):
                        ckpt.round_diagnostic_blocks += 1
                        requirement = " or ".join(diagnostic_tools)
                        if diagnostic_mode == "sandbox_only":
                            requirement += " and return finite numeric evidence in RESULT"
                        last_tool_res = {
                            "error_code": "stagnation_diagnostic_required",
                            "error": f"Call {requirement}, then resubmit the plan.",
                            "recommended_tools": list(diagnostic_tools),
                        }
                        if strict_diagnostic_gate:
                            last_tool_res["outer_steps_remaining"] = effective_outer_cap - ckpt.round_outer_requests
                            if diagnostic_mode == "sandbox_only":
                                repair_hint = next((
                                    event.get("repair_hint") for event in reversed(ckpt.trajectory_control_events)
                                    if event["round_id"] == r_id and event["event"] == "strict_sandbox_attempt"
                                ), None)
                                if repair_hint is not None:
                                    last_tool_res["repair_hint"] = repair_hint
                        else:
                            last_tool_res["remaining_blocks"] = 2 - ckpt.round_diagnostic_blocks
                        ckpt.trajectory_control_events.append({
                            "round_id": r_id,
                            "event": "stagnation_diagnostic_required",
                            "block": ckpt.round_diagnostic_blocks,
                        })
                        arguments = {key: value for key, value in dec.items() if key not in {"action", "tool_call_id"}}
                        _append_tool_result(messages, dec, "submit_plan_and_evolve", arguments, last_tool_res)
                        ckpt.round_step_index += 1
                        _save_ckpt()
                        continue
                    if budget.remaining is not None and budget.remaining <= 0:
                        ckpt.phase = "budget_stopped"
                        _save_ckpt()
                        break
                    chosen_tpl = str(dec.get("template_id") or ckpt.active_template_id)
                    chosen_pp = str(dec.get("postprocess_mode") or ckpt.active_postprocess_mode)
                    if not config.tools_enabled or chosen_tpl not in config.allowed_templates:
                        chosen_tpl = ckpt.active_template_id
                    if not config.tools_enabled or chosen_pp not in config.allowed_postprocess_modes:
                        chosen_pp = ckpt.active_postprocess_mode
                    if diagnostic_required:
                        _record_gate_bypass(r_id, "submit_after_two_blocks")
                    ckpt.round_plan_args = {
                        "template_id": chosen_tpl,
                        "postprocess_mode": chosen_pp,
                        "direction": str(dec.get("direction") or f"Round {r_id} search."),
                        "hypothesis": str(dec.get("hypothesis") or f"Round {r_id} optimization hypothesis."),
                        "cited_kb_ids": list(dec.get("cited_kb_ids") or []),
                        "rationale": str(dec.get("rationale") or ""),
                        **_plan_sandbox_evidence(),
                    }
                    if restart_trigger is not None or (restart_available and dec.get("fresh_template") is True):
                        ckpt.round_plan_args["fresh_template"] = True
                        if not deterministic_restart and not global_stopping_enabled:
                            ckpt.trajectory_control_events.append({
                                "round_id": r_id, "event": "basin_restart",
                            })
                    if dec.get("tool_call_id"):
                        ckpt.pending_submit_tool_call = {
                            "id": str(dec["tool_call_id"]),
                            "type": "function",
                            "function": {
                                "name": "submit_plan_and_evolve",
                                "arguments": json.dumps({
                                    key: value for key, value in ckpt.round_plan_args.items()
                                    if key != "sandbox_ref"
                                }, ensure_ascii=False),
                            },
                        }
                    else:
                        ckpt.pending_submit_tool_call = None
                    ckpt.phase = "session_evolve"
                    ckpt.round_step_index += 1
                    _save_ckpt()
                    break
                messages.append({
                    "role": "user",
                    "content": f"Invalid action '{act}' in diagnose phase ({dec.get('error', '')}). Call a valid diagnose tool or submit_plan_and_evolve.",
                })
                ckpt.round_step_index += 1
                _save_ckpt()
                continue

            if ckpt.phase == "budget_stopped":
                break
            if ckpt.phase == "diagnose":
                # Older checkpoints may have persisted a fallback plan before changing phase.
                if strict_diagnostic_gate and _diagnostic_required(r_id):
                    _stop_for_missing_diagnostic(r_id, "session_entry")
                    break
                ckpt.phase = "session_evolve"
                _save_ckpt()

        # Phase 2: Execute / Resume Official Session Runtime EoH Round
        session_out: dict[str, Any] = {}
        if ckpt.phase == "session_evolve":
            if strict_diagnostic_gate and _diagnostic_required(r_id):
                _stop_for_missing_diagnostic(r_id, "session_entry")
                break
            pargs = dict(ckpt.round_plan_args or {})
            if restart_trigger is not None:
                pargs["fresh_template"] = True
            if deterministic_restart or (global_stopping_enabled and pargs.get("fresh_template") is True):
                pargs.setdefault("session_requests_before", budget.used)
            ckpt.round_plan_args = pargs
            sandbox_evidence = {"sandbox_ref": pargs["sandbox_ref"]} if "sandbox_ref" in pargs else {}
            chosen_tpl = str(pargs.get("template_id") or ckpt.active_template_id)
            chosen_pp = str(pargs.get("postprocess_mode") or ckpt.active_postprocess_mode)
            ckpt.active_template_id = chosen_tpl
            ckpt.active_postprocess_mode = chosen_pp
            _save_ckpt()

            diag_ref_payload = None
            if last_diag and last_diag.get("artifact_ref") and last_diag.get("artifact_sha256"):
                diag_ref_payload = {
                    "path": last_diag["artifact_ref"],
                    "sha256": last_diag["artifact_sha256"],
                    "usage_role": "dev_selection",
                }
            try:
                session_out = session_tool.run_round(
                    round_id=r_id,
                    template_id=chosen_tpl,
                    postprocess_mode=chosen_pp,
                    direction=str(pargs.get("direction") or f"Round {r_id}"),
                    hypothesis=str(pargs.get("hypothesis") or f"Round {r_id} hypothesis"),
                    cited_kb_ids=(pargs.get("cited_kb_ids") or ()) if config.kb_enabled else (),
                    diagnostic_ref=diag_ref_payload,
                    rationale=str(pargs.get("rationale") or ""),
                    is_final_round=(r_id >= config.max_rounds),
                    eval_dev_suite=bool(config.eval_dev_suite),
                    fresh_template=pargs.get("fresh_template") is True,
                )
            except ProviderFailure:
                if config.strict_checkpoint_barriers:
                    _sync_strict_checkpoints(reconcile_orphans=True)
                _save_ckpt()
                raise
            ckpt.session_initialized = True
            ckpt.round_prev_best_dev = prev_best_dev
            ckpt.round_inner_requests = _round_inner_requests(session_out, budget.used)
            if deterministic_restart:
                ckpt.round_inner_requests = budget.used - pargs["session_requests_before"]
            if session_out.get("fresh_template_applied") is True and (restart_trigger is not None or global_stopping_enabled):
                restart_event = {"round_id": r_id, "event": "basin_restart", "trigger_round_id": r_id - 1}
                if restart_trigger is not None:
                    restart_event["stagnation_trigger_ordinal"] = restart_trigger.get("stagnation_trigger_ordinal")
                if global_stopping_enabled:
                    restart_event["request_ordinal"] = pargs["session_requests_before"]
                    ckpt.restart_eligible_round_id = None
                ckpt.trajectory_control_events.append(restart_event)

            # Record best dev frozen solver + archive stepping stones (enforce completion rate & penalized score)
            frozen = session_out.get("frozen_solver")
            dev_eval = session_out.get("dev_eval")
            best_obj = _extract_eval_objective(dev_eval)
            if frozen is not None:
                snap_rel = f"agent_artifacts/round_{r_id:04d}_frozen_solver.json"
                atomic_write_json(run_dir / snap_rel, frozen)
                valid_cnt = int(dev_eval.get("valid_count") or 0) if dev_eval is not None else 0
                if dev_eval is not None and best_obj is not None and valid_cnt > 0:
                    cand_all_feasible = bool(dev_eval.get("all_feasible", False))
                    cand_comp_rate = float(dev_eval.get("completion_rate") or 0.0)
                    cand_key = (cand_all_feasible, cand_comp_rate, -float(best_obj))
                    prev_key = (
                        bool(ckpt.best_all_feasible),
                        float(ckpt.best_completion_rate),
                        -(float(ckpt.best_dev_objective) if ckpt.best_dev_objective is not None else float("inf")),
                    )
                    if ckpt.best_solver_manifest_ref is None or cand_key > prev_key:
                        ckpt.best_all_feasible = cand_all_feasible
                        ckpt.best_completion_rate = cand_comp_rate
                        ckpt.best_dev_objective = float(best_obj)
                        ckpt.best_solver_manifest_ref = snap_rel
                if config.archive_feedback_enabled and dev_eval is not None:
                    archive_tool.register_solver_with_dev_records(
                        frozen_solver=frozen,
                        arm_id=config.arm_id,
                        search_seed=config.search_seed,
                        budget_id=f"{int(config.instance_time_budget_ms)}ms",
                        dev_records=dev_eval["records"],
                        mean_objective=best_obj,
                        solve_ms_mean=dev_eval.get("solve_ms_mean"),
                    )

            # Re-check checkpoints in case frozen solver improved right during this round
            if config.strict_checkpoint_barriers:
                _sync_strict_checkpoints(reconcile_orphans=True)
            else:
                for cp in session_out.get("crossed_checkpoints") or ():
                    _freeze_checkpoint(int(cp), int(budget.used))

            # Persist eval summary artifact so hypotheses and reflection can inspect & cite exact SHA-256
            regime_slices = None
            if config.tools_enabled and dev_eval and dev_eval.get("records"):
                from agent_skill_loop.interface_design.diagnostics import analyze_instance_records

                regime_slices = analyze_instance_records(
                    dev_eval["records"],
                    instance_metadata=archive_tool._inst_meta,
                )

            ev_art_rel = f"agent_artifacts/round_{r_id:04d}_dev_eval.json"
            # Task terminal facts can describe a round-local limit even when the Session continues.
            session_outcome = {key: session_out[key] for key in _SESSION_TERMINATION_FIELDS if session_out.get(key)}
            session_outcome.update({key: session_out[key] for key in _SESSION_TRAJECTORY_FIELDS if key in session_out})
            ev_art_sha = atomic_write_json(
                run_dir / ev_art_rel,
                {
                    "round_id": r_id,
                    "template_id": chosen_tpl,
                    "postprocess_mode": chosen_pp,
                    **sandbox_evidence,
                    **session_outcome,
                    "mean_tour_length": best_obj,
                    "penalized_mean_tour_length": best_obj,
                    "valid_only_mean_tour_length": dev_eval.get("valid_only_mean_tour_length") if dev_eval else None,
                    "valid_count": dev_eval.get("valid_count") if dev_eval else None,
                    "instance_count": dev_eval.get("instance_count") if dev_eval else None,
                    "completion_rate": dev_eval.get("completion_rate") if dev_eval else None,
                    "all_feasible": dev_eval.get("all_feasible") if dev_eval else None,
                    "failure_penalty_policy": dev_eval.get("failure_penalty_policy") if dev_eval else None,
                    "solve_ms_mean": dev_eval.get("solve_ms_mean") if dev_eval else None,
                    "frozen_solver_id": frozen.get("solver_id") if frozen else None,
                },
            )
            reflect_payload: dict[str, Any] = {
                "round_id": r_id,
                **session_outcome,
                "template_id": chosen_tpl,
                "postprocess_mode": chosen_pp,
                **sandbox_evidence,
                "eval_artifact_ref": ev_art_rel,
                "eval_artifact_sha256": ev_art_sha,
                "mean_tour_length": best_obj,
                "valid_only_mean_tour_length": dev_eval.get("valid_only_mean_tour_length") if dev_eval else None,
                "valid_count": dev_eval.get("valid_count") if dev_eval else None,
                "instance_count": dev_eval.get("instance_count") if dev_eval else None,
                "completion_rate": dev_eval.get("completion_rate") if dev_eval else None,
                "all_feasible": dev_eval.get("all_feasible") if dev_eval else None,
                "solve_ms_mean": dev_eval.get("solve_ms_mean") if dev_eval else None,
                "frozen_solver_id": frozen.get("solver_id") if frozen else None,
                "evolved_hook_preview": str(frozen.get("hook_code") or "")[:1200] if frozen else None,
                "regime_summary": (regime_slices or {}).get("by_factor") if isinstance(regime_slices, Mapping) else None,
            }
            last_tool_res = reflect_payload
            ckpt.pending_reflect_payload = reflect_payload
            ckpt.phase = "reflect"
            ckpt.round_reflect_requests = 0
            _save_ckpt()

        # Phase 3: Reflection & Hypothesis Ledger Update
        if ckpt.phase == "reflect":
            reflect_payload_now = ckpt.pending_reflect_payload or last_tool_res or {}
            if "session_status" not in reflect_payload_now:
                # Legacy reflect checkpoints recorded Session status only in the dev-eval artifact.
                legacy_eval = run_dir / "agent_artifacts" / f"round_{r_id:04d}_dev_eval.json"
                if legacy_eval.is_file():
                    eval_text = legacy_eval.read_text(encoding="utf-8")
                    if sha256_text(eval_text) == reflect_payload_now.get("eval_artifact_sha256"):
                        outcome = json.loads(eval_text)
                        reflect_payload_now = {**reflect_payload_now, **{
                            key: outcome[key] for key in _SESSION_TERMINATION_FIELDS if key in outcome
                        }}
            if reflect_payload_now:
                last_tool_res = dict(reflect_payload_now)
                if ckpt.pending_submit_tool_call and ckpt.pending_submit_tool_call.get("id"):
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [ckpt.pending_submit_tool_call],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": str(ckpt.pending_submit_tool_call["id"]),
                        "content": json.dumps(reflect_payload_now, ensure_ascii=False, default=str),
                    })
                    messages.append({
                        "role": "user",
                        "content": "Review the round evaluation above. If any open hypothesis was tested, call `hypothesis_update` citing `eval_artifact_ref` + `eval_artifact_sha256`, then call `finish_round`.",
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": json.dumps({"phase": "reflect", "round_evaluation_result": reflect_payload_now}, ensure_ascii=False, default=str),
                    })
            reflect_step = ckpt.round_reflect_requests
            pending_restart = (
                deterministic_restart and r_id < config.max_rounds
                and reflect_payload_now.get("stop_reason") == "stagnation_early_stop"
                and _session_terminal_phase(reflect_payload_now) is None
            )
            terminal_phase = _session_terminal_phase(reflect_payload_now)
            inner_stopped = reflect_payload_now.get("stop_reason") == "stagnation_early_stop"
            dev_obj = _extract_eval_objective(reflect_payload_now)
            global_decision = None
            if global_stopping_enabled and ckpt.round_reflect_requests == 0:
                previous = ckpt.trajectory_best_dev_objective
                pending_heuristic_restart = (
                    config.basin_restart_on_stagnation and not deterministic_restart and r_id < config.max_rounds
                    and (inner_stopped or dev_obj is None or (previous is not None and dev_obj >= previous))
                )
                decision = _global_stopping_at(
                    r_id, "session_early_stop" if inner_stopped else "session_end",
                    pending_restart=pending_restart or pending_heuristic_restart,
                    terminal_phase=terminal_phase,
                )
                if decision["stop"]:
                    global_decision = decision
            reflection_attempt_floor = _CONTROLLER_ATTEMPT_LIMIT if pending_restart else 0
            while (global_decision is None and not ckpt.round_reflection_finished
                   and ckpt.round_reflect_requests < config.outer_reflect_cap
                   and (budget.remaining is None or budget.remaining > reflection_attempt_floor)):
                try:
                    dec = driver.decide_step(
                        round_id=r_id,
                        phase="reflect",
                        step_index=reflect_step,
                        messages=messages,
                        last_tool_result=last_tool_res,
                    )
                except ProviderFailure:
                    if config.strict_checkpoint_barriers:
                        _sync_strict_checkpoints()
                    _save_ckpt()
                    raise
                if config.strict_checkpoint_barriers:
                    _sync_strict_checkpoints()
                act = str(dec.get("action") or "")
                if act == "budget_exhausted" and config.strict_checkpoint_barriers and dec.get("denial_reason") == "checkpoint_pending":
                    if budget.remaining is None or budget.remaining > 0:
                        _save_ckpt()
                        continue
                ckpt.round_reflect_requests += 1
                reflect_step += 1
                if act in {"finish_round", "budget_exhausted"}:
                    for upd in dec.get("hypothesis_updates") or ():
                        if isinstance(upd, Mapping):
                            try:
                                _dispatch_tool("hypothesis_update", upd, r_id)
                            except Exception:
                                pass
                    ckpt.round_reflection_finished = True
                    _save_ckpt()
                    break
                if act == "call_tool":
                    tname = str(dec["tool"])
                    targs = dict(dec.get("arguments") or {})
                    try:
                        tres = _dispatch_tool(tname, targs, r_id)
                    except Exception as exc:
                        tres = {"error": f"{type(exc).__name__}: {exc}"}
                    last_tool_res = tres
                    if dec.get("tool_call_id"):
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": str(dec["tool_call_id"]),
                                "type": "function",
                                "function": {"name": tname, "arguments": json.dumps(targs, ensure_ascii=False)},
                            }],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": str(dec["tool_call_id"]),
                            "content": json.dumps(tres, ensure_ascii=False, default=str),
                        })
                    else:
                        messages.append({"role": "assistant", "content": json.dumps(dec, ensure_ascii=False)})
                        messages.append({"role": "user", "content": json.dumps({"tool": tname, "result": tres}, ensure_ascii=False, default=str)})
                    _save_ckpt()
                    continue
                if act == "invalid_response":
                    messages.append({
                        "role": "user",
                        "content": f"Invalid response in reflect phase ({dec.get('error', '')}). Call hypothesis_update or finish_round.",
                    })
                    _save_ckpt()
                    continue
                break

            prev_cmp = ckpt.round_prev_best_dev
            delta_str = ""
            if dev_obj is not None and prev_cmp is not None:
                delta_str = f"{float(dev_obj) - float(prev_cmp):+.4f}"
            if dev_obj is not None and (prev_best_dev is None or float(dev_obj) < float(prev_best_dev)):
                prev_best_dev = float(dev_obj)

            if inner_stopped:
                event = {"round_id": r_id, "event": "stagnation_early_stop"}
                if "stagnation_trigger_ordinal" in reflect_payload_now:
                    event["stagnation_trigger_ordinal"] = reflect_payload_now["stagnation_trigger_ordinal"]
                ckpt.trajectory_control_events.append(event)
            if track_round_stagnation:
                previous = ckpt.trajectory_best_dev_objective
                if dev_obj is not None and (previous is None or dev_obj < previous):
                    ckpt.trajectory_best_dev_objective = dev_obj
                    ckpt.consecutive_stagnant_rounds = 0
                else:
                    ckpt.consecutive_stagnant_rounds += 1
                    ckpt.trajectory_control_events.append({
                        "round_id": r_id,
                        "event": "round_stagnant",
                        "consecutive_stagnant_rounds": ckpt.consecutive_stagnant_rounds,
                    })
                if deterministic_restart:
                    ckpt.restart_eligible_round_id = (
                        r_id + 1 if pending_restart and budget.remaining != 0 else None
                    )
                elif config.basin_restart_on_stagnation and (inner_stopped or ckpt.consecutive_stagnant_rounds >= 1):
                    ckpt.restart_eligible_round_id = r_id + 1
                else:
                    ckpt.restart_eligible_round_id = None

            if global_stopping_enabled and global_decision is None:
                decision = _global_stopping_at(
                    r_id, "round_end", pending_restart=pending_restart and budget.remaining != 0,
                    terminal_phase=terminal_phase,
                )
                if decision["stop"]:
                    global_decision = decision
            if global_decision is not None:
                _seal_global_champion(global_decision)

            h_counts = ledger_tool.counts()
            r_summary = {
                "round_id": r_id,
                "arm_id": config.arm_id,
                "problem_family": config.problem_family,
                "template_id": ckpt.active_template_id,
                "postprocess_mode": ckpt.active_postprocess_mode,
                "session_status": "resumed",
                **{key: reflect_payload_now[key] for key in ("sandbox_ref",) if key in reflect_payload_now},
                **{key: reflect_payload_now[key] for key in _SESSION_TERMINATION_FIELDS if key in reflect_payload_now},
                **{key: reflect_payload_now[key] for key in _SESSION_TRAJECTORY_FIELDS if key in reflect_payload_now},
                "best_objective": f"{dev_obj:.4f}" if dev_obj is not None else "",
                "delta_vs_prev": delta_str,
                "requests_used_total": budget.used,
                "attempted_request_delta": budget.used - (
                    int(round_summaries[-1]["requests_used_total"]) if round_summaries else 0
                ),
                "outer_requests_round": ckpt.round_outer_requests + ckpt.round_reflect_requests,
                "inner_requests_round": ckpt.round_inner_requests,
                "hypotheses_supported": h_counts.get("supported", 0),
                "hypotheses_refuted": h_counts.get("refuted", 0),
                "frozen_manifest_ref": ckpt.best_solver_manifest_ref or "",
            }
            consumption = session_tool.memory_consumption(r_id)
            r_summary["memory_consumption"] = consumption
            r_summary["feature_count"] = len(consumption["injected_refs"])
            append_results_tsv_row(tsv_path, r_summary)
            round_summaries.append(r_summary)
            ckpt.round_summaries.append(r_summary)
            ckpt.completed_rounds.append(r_id)
            ckpt.current_round += 1
            ckpt.phase = "early_stopped_global" if global_decision is not None else terminal_phase or "diagnose"
            ckpt.round_step_index = 0
            ckpt.round_outer_requests = 0
            ckpt.round_reflect_requests = 0
            ckpt.round_reflection_finished = False
            ckpt.round_inner_requests = 0
            ckpt.round_prev_best_dev = None
            ckpt.round_plan_args = None
            ckpt.round_diagnostic_called = False
            ckpt.round_diagnostic_blocks = 0
            ckpt.pending_reflect_payload = None
            ckpt.pending_submit_tool_call = None
            _save_ckpt()
            if ckpt.phase == "early_stopped_global":
                break

    budget.reconcile_orphaned_inflight()
    if config.strict_checkpoint_barriers:
        _sync_strict_checkpoints(reconcile_orphans=True)
    strict_gate_stop = ckpt.phase == "budget_stopped" and any(
        event["round_id"] == ckpt.current_round and event["event"] == "strict_diagnostic_gate_stopped"
        for event in ckpt.trajectory_control_events
    )
    has_champion = bool(ckpt.best_solver_manifest_ref and ckpt.best_dev_objective is not None)
    below_cap_completed = (
        budget.used < config.total_request_cap
        and ckpt.phase not in {"budget_stopped", "early_stopped_global"}
    )
    if config.strict_checkpoint_barriers and (not has_champion or below_cap_completed):
        with closing(sqlite3.connect(budget.ledger_path)) as con:
            row = con.execute(
                """SELECT solver_manifest_json, dev_penalized_mean, dev_completion_rate, dev_all_feasible
                   FROM candidate_provenance
                   WHERE run_id=? AND global_ordinal <= ? AND eligible=1 AND solver_manifest_json IS NOT NULL
                   ORDER BY dev_all_feasible DESC, dev_completion_rate DESC, dev_penalized_mean ASC, global_ordinal ASC
                   LIMIT 1""",
                (config.run_id, budget.used),
            ).fetchone()
        if row is not None and row[0] is not None:
            ref = "best_solver_manifest.json"
            atomic_write_json(run_dir / ref, json.loads(row[0]))
            ckpt.best_solver_manifest_ref = ref
            ckpt.best_dev_objective = float(row[1]) if row[1] is not None else None
            ckpt.best_completion_rate = float(row[2]) if row[2] is not None else 0.0
            ckpt.best_all_feasible = bool(row[3])
            has_champion = bool(ckpt.best_solver_manifest_ref and ckpt.best_dev_objective is not None)
    if not has_champion and not strict_gate_stop:
        ckpt.phase = "no_champion"
    elif ckpt.phase not in {"budget_stopped", "early_stopped_global"}:
        ckpt.phase = "completed"
    _save_ckpt()

    req_rows = budget.request_records()
    in_vals = [r["input_tokens"] for r in req_rows if r.get("input_tokens") is not None]
    out_vals = [r["output_tokens"] for r in req_rows if r.get("output_tokens") is not None]
    cached_vals = [r["cached_tokens"] for r in req_rows if r.get("cached_tokens") is not None]
    in_tokens_sum = sum(int(x) for x in in_vals)
    out_tokens_sum = sum(int(x) for x in out_vals)
    cached_tokens_sum = sum(int(x) for x in cached_vals) if cached_vals else None
    elapsed_sum = round(sum(float(r.get("elapsed_seconds") or 0.0) for r in req_rows), 3)
    state_counts: dict[str, int] = {}
    req_models: dict[str, int] = {}
    served_models: dict[str, int] = {}
    for r in req_rows:
        st_name = str(r.get("state") or "unknown")
        state_counts[st_name] = state_counts.get(st_name, 0) + 1
        rm = r.get("requested_model") or r.get("model")
        if rm:
            req_models[str(rm)] = req_models.get(str(rm), 0) + 1
        sm = r.get("served_model")
        if sm:
            served_models[str(sm)] = served_models.get(str(sm), 0) + 1

    policy = ModelRoutingPolicy.from_dict(config.model_routing_policy)
    eff_rate_card = config.rate_card if config.rate_card is not None else policy.rate_card
    eff_rc_ver = config.rate_card_version or policy.rate_card_version
    cost_summary = price_ledger_records_with_rate_card(
        budget.ledger_path,
        config.run_id,
        eff_rate_card,
        rate_card_version=eff_rc_ver,
    )
    token_summary = {
        "input_tokens": in_tokens_sum,
        "output_tokens": out_tokens_sum,
        "cached_tokens": cached_tokens_sum,
        "cached_tokens_reported_count": len(cached_vals),
        "total_tokens": in_tokens_sum + out_tokens_sum,
        "provider_elapsed_seconds": elapsed_sum,
        "outer_requests": sum(1 for r in req_rows if r.get("purpose") in {"planner", "reflection"}),
        "inner_eoh_requests": sum(1 for r in req_rows if r.get("purpose") not in {"planner", "reflection"}),
        "state_counts": state_counts,
        "requested_models": req_models,
        "served_models": served_models,
        "barrier_rejections": getattr(budget, "barrier_rejections", 0),
    }

    milestone_status = read_milestone_status(budget.ledger_path, config.run_id) if config.strict_checkpoint_barriers else None
    last_round = round_summaries[-1] if round_summaries else {}
    if ckpt.phase == "early_stopped_global":
        stop_reason = "global_early_stop_" + config.global_early_stop_mode
    elif strict_gate_stop:
        stop_reason = "strict_diagnostic_gate_stopped"
    elif budget.remaining == 0:
        stop_reason = "request_budget_exhausted"
    elif last_round.get("completion_reason"):
        stop_reason = last_round["completion_reason"]
    elif ckpt.current_round > config.max_rounds:
        stop_reason = "max_rounds_reached"
    else:
        stop_reason = last_round.get("stop_reason") or ckpt.phase

    final_summary = {
        "schema_version": "m3-research-summary/v1",
        "run_id": config.run_id,
        "arm_id": config.arm_id,
        "problem_family": config.problem_family,
        "final_phase": ckpt.phase,
        "stop_reason": stop_reason,
        "restart_count": sum(event["event"] == "basin_restart" for event in ckpt.trajectory_control_events),
        "realized_request_spend": len(req_rows),
        "completed_rounds": list(ckpt.completed_rounds),
        "best_dev_objective": ckpt.best_dev_objective,
        "best_solver_manifest_ref": ckpt.best_solver_manifest_ref,
        "frozen_checkpoints": dict(ckpt.frozen_checkpoints),
        "budget_summary": budget.summary(),
        "token_summary": token_summary,
        "cost_summary": cost_summary,
        "milestone_status": milestone_status,
        "hypothesis_counts": ledger_tool.counts(),
        "archive_summary": archive_tool.summary() if config.archive_feedback_enabled else None,
        "round_summaries": round_summaries,
        "memory_consumption": [row["memory_consumption"] for row in round_summaries if "memory_consumption" in row],
        "feature_count": sum(row.get("feature_count", 0) for row in round_summaries),
        "trajectory_control_events": list(ckpt.trajectory_control_events),
        "last_sandbox_ref": ckpt.last_sandbox_ref,
        "sandbox_success_count": ckpt.sandbox_success_count,
        "gate_bypass_count": ckpt.gate_bypass_count,
        "gate_bypass_events": list(ckpt.gate_bypass_events),
        "completed_at": utc_now(),
    }
    atomic_write_json(run_dir / "research_summary.json", final_summary)
    return final_summary
