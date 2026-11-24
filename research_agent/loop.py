"""Main crash-recoverable autonomous Research Agent loop orchestrating Session Runtime."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.model_routing import ModelRoutingPolicy
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver, resolve_problem_adapter
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
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
from research_agent.tools.math_sandbox import MathSandboxTool
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
        if val is not None and not isinstance(val, bool) and isinstance(val, (int, float)):
            return float(val)
    return None


def _build_initial_baseline_solver(config: AgentConfig) -> FrozenInterfaceSolver:
    tpl = get_template_spec(config.initial_template_id, "v1")
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
        template_options={"inject_static_kb_clues": bool(config.inject_static_kb_clues)},
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
    resume: bool = False,
) -> dict[str, Any]:
    """Run or crash-resume the autonomous Research Agent across multi-round Session execution."""
    run_dir = Path(config.output_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = run_dir / "agent_config.json"
    ckpt_path = run_dir / "agent_checkpoint.json"
    policy_path = run_dir / "research_policy.md"
    tsv_path = run_dir / "results.tsv"

    if not resume and ckpt_path.exists():
        raise FileExistsError(f"research_agent_checkpoint_already_exists:{ckpt_path}")

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
        )
        for field_name in immutable_fields:
            if getattr(persisted_cfg, field_name) != getattr(config, field_name):
                raise ValueError(
                    f"resume_config_mismatch:{field_name}:{getattr(persisted_cfg, field_name)}!={getattr(config, field_name)}"
                )
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

    kb_tool = KnowledgeBaseTool(run_dir, kb_store_path=config.kb_store_path)
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
    session_tool = SessionRunnerTool(run_dir=run_dir, config=config, budget=budget)

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

    def _sync_strict_checkpoints() -> None:
        if not config.strict_checkpoint_barriers:
            return
        total_wall = _flush_wall_clock()
        settle_pending_provenance_for_terminal_requests(budget.ledger_path, config.run_id)
        try_seal_draining_checkpoints(
            budget.ledger_path,
            config.run_id,
            wall_elapsed_seconds=total_wall,
        )
        exported = export_sealed_checkpoints(budget.ledger_path, config.run_id, run_dir / "checkpoints")
        for cp_key, abs_path in exported.items():
            ckpt.frozen_checkpoints[cp_key] = str(Path(abs_path).resolve().relative_to(run_dir).as_posix())

    if config.strict_checkpoint_barriers:
        mstatus = read_milestone_status(budget.ledger_path, config.run_id)
        if not mstatus["checkpoints"]:
            session_tool.ensure_initialized()
            baseline_solver = _build_initial_baseline_solver(config)
            if config.use_benchmark_dev_suite:
                suite_obj = load_dev_or_public_suite(
                    config.dev_suite_id,
                    split=config.dev_split,
                    role="diagnostic_interactive",
                )
                base_dev_eval = session_tool._evaluate_frozen_on_dev(baseline_solver.to_dict())
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
                }
            dev_suite_hash = sha256_text(
                json.dumps(suite_obj["instances"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            )
            initialize_milestone_schedule(
                budget.ledger_path,
                run_id=config.run_id,
                checkpoint_budgets=config.checkpoint_budgets,
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
        _sync_strict_checkpoints()

    _save_ckpt()

    last_sandbox: dict[str, Any] | None = None
    last_diag: dict[str, Any] | None = None
    prev_best_dev: float | None = ckpt.best_dev_objective
    round_summaries: list[dict[str, Any]] = list(ckpt.round_summaries)

    def _dispatch_tool(tool_name: str, args: Mapping[str, Any], round_id: int) -> dict[str, Any]:
        nonlocal last_sandbox, last_diag
        if not config.tools_enabled and tool_name not in {"hypothesis_propose", "hypothesis_update"}:
            raise PermissionError(f"tool_disabled_in_arm:{tool_name}")
        if tool_name == "kb_search":
            return kb_tool.search(query=str(args.get("query", "")), limit=int(args.get("limit", 5)), problem_family=config.problem_family)
        if tool_name == "kb_read":
            return kb_tool.read(entry_id=str(args["entry_id"]))
        if tool_name == "diagnose_suite":
            res = diag_tool.diagnose_suite(
                template_id=str(args.get("template_id") or ckpt.active_template_id),
                hook_code=args.get("hook_code"),
                postprocess_mode=str(args.get("postprocess_mode") or ckpt.active_postprocess_mode),
                time_budget_ms=float(args.get("time_budget_ms") or config.instance_time_budget_ms),
                max_instances=args.get("max_instances"),
            )
            last_diag = res
            return res
        if tool_name == "run_math_sandbox":
            res = sandbox_tool.run(script=str(args["script"]))
            last_sandbox = res
            return res
        if tool_name == "list_interfaces":
            return iface_tool.list_interfaces()
        if tool_name == "propose_and_validate_interface":
            return iface_tool.propose_and_validate(
                template_id=str(args["template_id"]),
                postprocess_mode=str(args.get("postprocess_mode", "none")),
                time_budget_ms=float(args.get("time_budget_ms") or config.instance_time_budget_ms),
                diagnostic_ref=args.get("diagnostic_ref"),
                rationale=str(args.get("rationale", "")),
            )
        if tool_name == "archive_summary":
            return archive_tool.summary()
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
                last_sandbox=last_sandbox,
                last_diag=last_diag,
            )
            return ledger_tool.update(
                hypothesis_id=str(args["hypothesis_id"]),
                status=str(args["status"]),
                rationale=str(args.get("rationale", "")),
                evidence_artifacts=refs,
            )
        raise ValueError(f"unknown_tool:{tool_name}")

    while ckpt.current_round <= config.max_rounds:
        r_id = ckpt.current_round
        if r_id in ckpt.completed_rounds:
            ckpt.current_round += 1
            ckpt.phase = "diagnose"
            ckpt.round_step_index = 0
            ckpt.round_outer_requests = 0
            ckpt.round_reflect_requests = 0
            ckpt.round_inner_requests = 0
            ckpt.round_prev_best_dev = None
            ckpt.round_plan_args = None
            _save_ckpt()
            continue

        if budget.remaining is not None and budget.remaining <= 0 and ckpt.phase == "diagnose":
            ckpt.phase = "budget_stopped"
            _save_ckpt()
            break

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": build_round_observation_message(
                    round_id=r_id,
                    budget_remaining=budget.remaining,
                    active_template_id=ckpt.active_template_id,
                    active_postprocess_mode=ckpt.active_postprocess_mode,
                    archive_state=archive_tool.summary() if config.archive_feedback_enabled else None,
                    previous_round_summary=round_summaries[-1] if round_summaries else None,
                    open_hypotheses=ledger_tool.list_records(),
                ),
            }
        ]
        last_tool_res: dict[str, Any] | None = None

        # Phase 1: Diagnose & Plan
        if ckpt.phase == "diagnose":
            while ckpt.round_plan_args is None:
                if ckpt.round_outer_requests >= config.outer_requests_per_round_cap:
                    ckpt.round_plan_args = {
                        "template_id": ckpt.active_template_id,
                        "postprocess_mode": ckpt.active_postprocess_mode,
                        "direction": f"Fallback plan for round {r_id} after reaching outer step cap.",
                        "hypothesis": f"Evolve {ckpt.active_template_id} within remaining EoH budget.",
                        "cited_kb_ids": [],
                        "rationale": "Outer round cap reached.",
                    }
                    _save_ckpt()
                    break

                if budget.remaining is not None and budget.remaining <= 0:
                    ckpt.phase = "budget_stopped"
                    _save_ckpt()
                    break

                if ckpt.round_outer_requests == config.outer_requests_per_round_cap - 1 and ckpt.round_outer_requests > 0:
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
                if act == "budget_exhausted":
                    if (
                        config.strict_checkpoint_barriers
                        and dec.get("denial_reason") == "checkpoint_pending"
                        and (budget.remaining is None or budget.remaining > 0)
                    ):
                        _sync_strict_checkpoints()
                        _save_ckpt()
                        continue
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
                    ckpt.round_step_index += 1
                    _save_ckpt()
                    continue
                if act == "submit_plan":
                    chosen_tpl = str(dec.get("template_id") or ckpt.active_template_id)
                    chosen_pp = str(dec.get("postprocess_mode") or ckpt.active_postprocess_mode)
                    if not config.tools_enabled or chosen_tpl not in config.allowed_templates:
                        chosen_tpl = ckpt.active_template_id
                    if not config.tools_enabled or chosen_pp not in config.allowed_postprocess_modes:
                        chosen_pp = ckpt.active_postprocess_mode
                    ckpt.round_plan_args = {
                        "template_id": chosen_tpl,
                        "postprocess_mode": chosen_pp,
                        "direction": str(dec.get("direction") or f"Round {r_id} search."),
                        "hypothesis": str(dec.get("hypothesis") or f"Round {r_id} optimization hypothesis."),
                        "cited_kb_ids": list(dec.get("cited_kb_ids") or []),
                        "rationale": str(dec.get("rationale") or ""),
                    }
                    if dec.get("tool_call_id"):
                        ckpt.pending_submit_tool_call = {
                            "id": str(dec["tool_call_id"]),
                            "type": "function",
                            "function": {
                                "name": "submit_plan_and_evolve",
                                "arguments": json.dumps(ckpt.round_plan_args, ensure_ascii=False),
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
            ckpt.phase = "session_evolve"
            _save_ckpt()

        # Phase 2: Execute / Resume Official Session Runtime EoH Round
        session_out: dict[str, Any] = {}
        if ckpt.phase == "session_evolve":
            pargs = dict(ckpt.round_plan_args or {})
            chosen_tpl = str(pargs.get("template_id") or ckpt.active_template_id)
            chosen_pp = str(pargs.get("postprocess_mode") or ckpt.active_postprocess_mode)
            ckpt.active_template_id = chosen_tpl
            ckpt.active_postprocess_mode = chosen_pp
            _save_ckpt()

            diag_ref_payload = None
            if last_diag is not None:
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
                    cited_kb_ids=pargs.get("cited_kb_ids") or (),
                    diagnostic_ref=diag_ref_payload,
                    rationale=str(pargs.get("rationale") or ""),
                    is_final_round=(r_id >= config.max_rounds),
                    eval_dev_suite=bool(config.eval_dev_suite),
                )
            except ProviderFailure:
                if config.strict_checkpoint_barriers:
                    _sync_strict_checkpoints()
                _save_ckpt()
                raise
            ckpt.session_initialized = True
            ckpt.round_prev_best_dev = prev_best_dev
            ckpt.round_inner_requests = _round_inner_requests(session_out, budget.used)

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
                _sync_strict_checkpoints()
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
            ev_art_sha = atomic_write_json(
                run_dir / ev_art_rel,
                {
                    "round_id": r_id,
                    "template_id": chosen_tpl,
                    "postprocess_mode": chosen_pp,
                    "session_status": session_out.get("session_status"),
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
                "template_id": chosen_tpl,
                "postprocess_mode": chosen_pp,
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
            reflect_payload_now = ckpt.pending_reflect_payload or last_tool_res
            if reflect_payload_now is not None:
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
            reflect_step = 0
            while ckpt.round_reflect_requests < config.outer_reflect_cap and (budget.remaining is None or budget.remaining > 0):
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

            dev_obj = _extract_eval_objective(session_out.get("dev_eval")) if session_out else (
                _extract_eval_objective(reflect_payload_now)
            )
            prev_cmp = prev_best_dev if session_out else ckpt.round_prev_best_dev
            delta_str = ""
            if dev_obj is not None and prev_cmp is not None:
                delta_str = f"{float(dev_obj) - float(prev_cmp):+.4f}"
            if dev_obj is not None and (prev_best_dev is None or float(dev_obj) < float(prev_best_dev)):
                prev_best_dev = float(dev_obj)

            h_counts = ledger_tool.counts()
            inner_used = (
                _round_inner_requests(session_out, budget.used)
                if session_out
                else int(ckpt.round_inner_requests or 0)
            )
            r_summary = {
                "round_id": r_id,
                "arm_id": config.arm_id,
                "problem_family": config.problem_family,
                "template_id": ckpt.active_template_id,
                "postprocess_mode": ckpt.active_postprocess_mode,
                "session_status": session_out.get("session_status") if session_out else "resumed",
                "best_objective": f"{dev_obj:.4f}" if dev_obj is not None else "",
                "delta_vs_prev": delta_str,
                "requests_used_total": budget.used,
                "outer_requests_round": ckpt.round_outer_requests + ckpt.round_reflect_requests,
                "inner_requests_round": inner_used,
                "hypotheses_supported": h_counts.get("supported", 0),
                "hypotheses_refuted": h_counts.get("refuted", 0),
                "frozen_manifest_ref": ckpt.best_solver_manifest_ref or "",
            }
            append_results_tsv_row(tsv_path, r_summary)
            round_summaries.append(r_summary)
            ckpt.round_summaries.append(r_summary)
            ckpt.completed_rounds.append(r_id)
            ckpt.current_round += 1
            ckpt.phase = "diagnose"
            ckpt.round_step_index = 0
            ckpt.round_outer_requests = 0
            ckpt.round_reflect_requests = 0
            ckpt.round_inner_requests = 0
            ckpt.round_prev_best_dev = None
            ckpt.round_plan_args = None
            ckpt.pending_reflect_payload = None
            ckpt.pending_submit_tool_call = None
            _save_ckpt()

    if config.strict_checkpoint_barriers:
        _sync_strict_checkpoints()
    has_champion = bool(ckpt.best_solver_manifest_ref and ckpt.best_dev_objective is not None)
    if not has_champion:
        ckpt.phase = "no_champion"
    elif ckpt.phase != "budget_stopped":
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

    final_summary = {
        "schema_version": "m3-research-summary/v1",
        "run_id": config.run_id,
        "arm_id": config.arm_id,
        "problem_family": config.problem_family,
        "final_phase": ckpt.phase,
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
        "completed_at": utc_now(),
    }
    atomic_write_json(run_dir / "research_summary.json", final_summary)
    return final_summary
