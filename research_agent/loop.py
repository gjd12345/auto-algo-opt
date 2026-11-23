"""Main crash-recoverable autonomous Research Agent loop orchestrating Session Runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent.contracts import (
    AgentCheckpoint,
    AgentConfig,
    append_results_tsv_row,
    atomic_write_json,
    atomic_write_text,
    sha256_file,
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

    def _freeze_checkpoint(ckpt_budget: int, used_now: int) -> None:
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
        on_checkpoint=_freeze_checkpoint,
        reconcile_inflight=True,
    )

    kb_tool = KnowledgeBaseTool(run_dir)
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

    def _save_ckpt() -> None:
        atomic_write_json(ckpt_path, ckpt.to_dict())

    _save_ckpt()

    last_sandbox: dict[str, Any] | None = None
    last_diag: dict[str, Any] | None = None
    prev_best_dev: float | None = ckpt.best_dev_objective
    round_summaries: list[dict[str, Any]] = []

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

                dec = driver.decide_step(
                    round_id=r_id,
                    phase="diagnose",
                    step_index=ckpt.round_step_index,
                    messages=messages,
                    last_tool_result=last_tool_res,
                )
                ckpt.round_outer_requests += 1
                act = str(dec.get("action") or "")
                if act == "budget_exhausted":
                    ckpt.phase = "budget_stopped"
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
                    ckpt.phase = "session_evolve"
                    ckpt.round_step_index += 1
                    _save_ckpt()
                    break
                raise ValueError(f"unexpected_driver_action_in_diagnose:{act}")

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
                eval_dev_suite=True,
            )
            ckpt.session_initialized = True

            # Record best dev frozen solver + archive stepping stones
            frozen = session_out.get("frozen_solver")
            dev_eval = session_out.get("dev_eval")
            best_obj = dev_eval.get("mean_tour_length") if dev_eval else None
            if frozen is not None:
                snap_rel = f"agent_artifacts/round_{r_id:04d}_frozen_solver.json"
                atomic_write_json(run_dir / snap_rel, frozen)
                if ckpt.best_dev_objective is None or (best_obj is not None and float(best_obj) < float(ckpt.best_dev_objective)):
                    ckpt.best_dev_objective = float(best_obj) if best_obj is not None else ckpt.best_dev_objective
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
            for cp in session_out.get("crossed_checkpoints") or ():
                _freeze_checkpoint(int(cp), int(budget.used))

            # Persist eval summary artifact so hypotheses can cite its SHA-256
            ev_art_rel = f"agent_artifacts/round_{r_id:04d}_dev_eval.json"
            ev_art_sha = atomic_write_json(
                run_dir / ev_art_rel,
                {
                    "round_id": r_id,
                    "template_id": chosen_tpl,
                    "postprocess_mode": chosen_pp,
                    "session_status": session_out.get("session_status"),
                    "mean_tour_length": best_obj,
                    "solve_ms_mean": dev_eval.get("solve_ms_mean") if dev_eval else None,
                    "frozen_solver_id": frozen.get("solver_id") if frozen else None,
                },
            )
            last_tool_res = {
                "round_id": r_id,
                "eval_artifact_ref": ev_art_rel,
                "eval_artifact_sha256": ev_art_sha,
                "mean_tour_length": best_obj,
            }
            ckpt.phase = "reflect"
            ckpt.round_reflect_requests = 0
            _save_ckpt()

        # Phase 3: Reflection & Hypothesis Ledger Update
        if ckpt.phase == "reflect":
            reflect_step = 0
            while ckpt.round_reflect_requests < config.outer_reflect_cap and (budget.remaining is None or budget.remaining > 0):
                dec = driver.decide_step(
                    round_id=r_id,
                    phase="reflect",
                    step_index=reflect_step,
                    messages=messages,
                    last_tool_result=last_tool_res,
                )
                ckpt.round_reflect_requests += 1
                reflect_step += 1
                act = str(dec.get("action") or "")
                if act in {"finish_round", "budget_exhausted"}:
                    break
                if act == "call_tool":
                    tres = _dispatch_tool(str(dec["tool"]), dict(dec.get("arguments") or {}), r_id)
                    last_tool_res = tres
                    _save_ckpt()
                    continue
                break

            dev_obj = (session_out.get("dev_eval") or {}).get("mean_tour_length") if session_out else None
            delta_str = ""
            if dev_obj is not None and prev_best_dev is not None:
                delta_str = f"{float(dev_obj) - float(prev_best_dev):+.4f}"
            if dev_obj is not None and (prev_best_dev is None or float(dev_obj) < float(prev_best_dev)):
                prev_best_dev = float(dev_obj)

            h_counts = ledger_tool.counts()
            inner_used = int((session_out.get("requests_after") or budget.used) - (session_out.get("requests_before") or budget.used)) if session_out else 0
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
            ckpt.completed_rounds.append(r_id)
            ckpt.current_round += 1
            ckpt.phase = "diagnose"
            ckpt.round_step_index = 0
            ckpt.round_outer_requests = 0
            ckpt.round_reflect_requests = 0
            ckpt.round_plan_args = None
            _save_ckpt()

    if ckpt.phase != "budget_stopped":
        ckpt.phase = "completed"
    _save_ckpt()

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
        "hypothesis_counts": ledger_tool.counts(),
        "archive_summary": archive_tool.summary() if config.archive_feedback_enabled else None,
        "round_summaries": round_summaries,
        "completed_at": utc_now(),
    }
    atomic_write_json(run_dir / "research_summary.json", final_summary)
    return final_summary
