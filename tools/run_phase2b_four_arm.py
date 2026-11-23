"""Phase 2B Step 2: Paired Multi-Seed Four-Arm (+ LLM vs Rule Planner) Fair-Budget Comparison.

All arms share the exact same:
- LLM model (deepseek-v4.1-flash via OpenCode Go)
- Total evolution sample budget B (default B=12) and request cap
- Candidate template versions, 5-gate validator, M1 verifier, and target instance time budget

Arms compared across paired independent search seeds (default: 20261122, 20261123):
  1. fixed_pointwise          : full budget B on cvrp_sequential_construct/v1
  2. dev_fixed_strong         : full budget B on dev-selected strong template (default L2a or L2b)
  3. short_pilot_racing       : K=3 x b=2 pilot + remaining B-6 continuation seeded by pilot winner
  4a. diagnostic_rule_planner : 0-token deterministic rule reading 2x3 diagnostic + target-budget probe -> full B
  4b. llm_diagnostic_planner  : 1-request LLM planner reading exact same diagnostic + probe -> remaining B-1

Supports both standard_500ms and tight_25ms to validate Protocol T1 (budget-aware adaptation).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from agent_skill_loop.cvrp_workbench.runner import run_frozen_workbench_bundle
from agent_skill_loop.request_budget import RequestBudget
from agent_skill_loop.interface_design.archive import ComplementaryArchive, compute_portfolio_complementarity
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.dynamic_eoh import run_dynamic_eoh_evolution
from agent_skill_loop.interface_design.planner import (
    KB_ROUND_CONTEXT_BY_TEMPLATE,
    build_design_for_template,
    probe_template_budget_headroom,
    run_short_pilot_racing,
    select_interface_by_diagnostic_rule,
    select_interface_by_llm_planner,
)
from frontend.build_dashboard import build_dashboard


def _run_seed_arm(
    arm_id: str,
    seed: int,
    *,
    out_root: Path,
    budget_id: str,
    target_budget_ms: float,
    total_samples: int,
    pilot_samples: int,
    total_request_cap: int,
    strong_template_id: str,
    endpoint: str,
    model: str,
    api_key_env: str,
    diag_doc: dict[str, Any],
    diag_ref: dict[str, Any],
    budget_probe: dict[str, Any],
) -> dict[str, Any]:
    arm_dir = out_root / budget_id / f"seed_{seed}" / arm_id
    arm_dir.mkdir(parents=True, exist_ok=False)
    arm_cache = arm_dir / "arm_result.json"
    solver_id = f"m2_2b_{budget_id}_{arm_id}_s{seed}"
    t0 = time.perf_counter()

    def _save_and_return(payload: dict[str, Any]) -> dict[str, Any]:
        arm_cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return payload

    if arm_id == "fixed_pointwise":
        design = build_design_for_template("cvrp_sequential_construct", "v1", design_id=solver_id, diagnostic_ref=diag_ref)
        res = run_dynamic_eoh_evolution(
            design=design,
            output_dir=arm_dir,
            pop_size=3,
            n_pop=max(1, total_samples // 3),
            max_sample_nums=total_samples,
            operators=("e1", "e2", "m1", "m2"),
            search_seed=seed,
            instance_time_budget_ms=target_budget_ms,
            solver_id=solver_id,
            display_name=f"Arm1 Pointwise (s{seed})",
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            max_requests=total_request_cap,
            require_evolved=True,
            round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(design.template_id),
        )
        return _save_and_return({
            "arm_id": arm_id,
            "seed": seed,
            "selected_template_id": "cvrp_sequential_construct",
            "planning_requests": 0,
            "planning_input_tokens": 0,
            "planning_output_tokens": 0,
            "diagnostic_probe_wall_ms": 0.0,
            "eoh_requests": res["resource_ledger"]["requests"],
            "best_dev24": res["best_objective"],
            "wall_s": round(time.perf_counter() - t0, 2),
            "frozen_solver": res["frozen_solver"],
        })

    if arm_id == "dev_fixed_strong":
        design = build_design_for_template(strong_template_id, "v1", design_id=solver_id, diagnostic_ref=diag_ref)
        res = run_dynamic_eoh_evolution(
            design=design,
            output_dir=arm_dir,
            pop_size=3,
            n_pop=max(1, total_samples // 3),
            max_sample_nums=total_samples,
            operators=("e1", "e2", "m1", "m2"),
            search_seed=seed,
            instance_time_budget_ms=target_budget_ms,
            solver_id=solver_id,
            display_name=f"Arm2 DevFixed ({strong_template_id}, s{seed})",
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            max_requests=total_request_cap,
            require_evolved=True,
            round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(design.template_id),
        )
        return _save_and_return({
            "arm_id": arm_id,
            "seed": seed,
            "selected_template_id": strong_template_id,
            "planning_requests": 0,
            "planning_input_tokens": 0,
            "planning_output_tokens": 0,
            "diagnostic_probe_wall_ms": 0.0,
            "eoh_requests": res["resource_ledger"]["requests"],
            "best_dev24": res["best_objective"],
            "wall_s": round(time.perf_counter() - t0, 2),
            "frozen_solver": res["frozen_solver"],
        })

    if arm_id == "short_pilot_racing":
        res = run_short_pilot_racing(
            output_dir=arm_dir,
            total_sample_budget=total_samples,
            pilot_samples_per_arm=pilot_samples,
            total_request_cap=total_request_cap,
            instance_time_budget_ms=target_budget_ms,
            search_seed=seed,
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            diagnostic_ref=diag_ref,
            solver_id_prefix=solver_id,
        )
        frozen = dict(res["frozen_solver"])
        frozen["solver_id"] = solver_id
        frozen["display_name"] = f"Arm3 Racing ({res['selected_template_id']}, s{seed})"
        return _save_and_return({
            "arm_id": arm_id,
            "seed": seed,
            "selected_template_id": res["selected_template_id"],
            "planning_requests": 0,
            "planning_input_tokens": 0,
            "planning_output_tokens": 0,
            "diagnostic_probe_wall_ms": 0.0,
            "eoh_requests": res["racing_ledger"]["requests"],
            "pilot_results": res["racing_ledger"]["pilot_results"],
            "best_dev24": res["best_objective"],
            "wall_s": round(time.perf_counter() - t0, 2),
            "frozen_solver": frozen,
        })

    if arm_id == "diagnostic_rule_planner":
        plan = select_interface_by_diagnostic_rule(
            diagnostic_summary=diag_doc,
            budget_probe=budget_probe,
            target_budget_ms=target_budget_ms,
            diagnostic_ref=diag_ref,
        )
        (arm_dir / "plan_decision.json").write_text(
            json.dumps({k: v for k, v in plan.items() if k != "design"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        res = run_dynamic_eoh_evolution(
            design=plan["design"],
            output_dir=arm_dir,
            pop_size=3,
            n_pop=max(1, total_samples // 3),
            max_sample_nums=total_samples,
            operators=("e1", "e2", "m1", "m2"),
            search_seed=seed,
            instance_time_budget_ms=target_budget_ms,
            solver_id=solver_id,
            display_name=f"Arm4a DiagRule ({plan['selected_template_id']}, s{seed})",
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            max_requests=total_request_cap,
            require_evolved=True,
            round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(plan["design"].template_id),
        )
        return _save_and_return({
            "arm_id": arm_id,
            "seed": seed,
            "selected_template_id": plan["selected_template_id"],
            "decision_trace": plan["decision_trace"],
            "planning_requests": 0,
            "planning_input_tokens": 0,
            "planning_output_tokens": 0,
            "diagnostic_probe_wall_ms": plan["diagnostic_probe_wall_ms"],
            "eoh_requests": res["resource_ledger"]["requests"],
            "best_dev24": res["best_objective"],
            "wall_s": round(time.perf_counter() - t0, 2),
            "frozen_solver": res["frozen_solver"],
        })

    if arm_id == "llm_diagnostic_planner":
        request_budget = RequestBudget(total_request_cap)
        plan = select_interface_by_llm_planner(
            diagnostic_summary=diag_doc,
            budget_probe=budget_probe,
            target_budget_ms=target_budget_ms,
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            diagnostic_ref=diag_ref,
            request_budget=request_budget,
        )
        (arm_dir / "plan_decision.json").write_text(
            json.dumps({k: v for k, v in plan.items() if k != "design"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # Count planner retries against the same outbound request cap.
        rem_samples = max(1, total_samples - 1)
        rem_requests = request_budget.remaining
        if rem_requests == 0:
            raise RuntimeError("planning_exhausted_arm_request_budget")
        res = run_dynamic_eoh_evolution(
            design=plan["design"],
            output_dir=arm_dir,
            pop_size=3,
            n_pop=max(1, rem_samples // 3),
            max_sample_nums=rem_samples,
            operators=("e1", "e2", "m1", "m2"),
            search_seed=seed,
            instance_time_budget_ms=target_budget_ms,
            solver_id=solver_id,
            display_name=f"Arm4b LLMPlan ({plan['selected_template_id']}, s{seed})",
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            max_requests=rem_requests,
            request_budget=request_budget,
            require_evolved=True,
            round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(plan["design"].template_id),
        )
        return _save_and_return({
            "arm_id": arm_id,
            "seed": seed,
            "selected_template_id": plan["selected_template_id"],
            "rationale": plan["rationale"],
            "planning_requests": plan["planning_requests"],
            "planning_request_attempts": plan["planning_request_attempts"],
            "planning_input_tokens": plan["planning_input_tokens"],
            "planning_output_tokens": plan["planning_output_tokens"],
            "planning_wall_ms": plan["planning_wall_ms"],
            "diagnostic_probe_wall_ms": plan["diagnostic_probe_wall_ms"],
            "eoh_requests": res["resource_ledger"]["requests"],
            "best_dev24": res["best_objective"],
            "wall_s": round(time.perf_counter() - t0, 2),
            "frozen_solver": res["frozen_solver"],
        })

    raise ValueError(f"unknown_arm_id:{arm_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=_REPO / "experiments" / "milestone2" / "phase2b_four_arm")
    parser.add_argument("--endpoint", default="https://opencode.ai/zen/go/v1/chat/completions")
    parser.add_argument("--model", default="deepseek-v4.1-flash")
    parser.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    parser.add_argument("--budget-id", default="standard_500ms")
    parser.add_argument("--target-budget-ms", type=float, default=500.0)
    parser.add_argument("--strong-template-id", default="cvrp_parallel_merge_static")
    parser.add_argument("--total-samples", type=int, default=12)
    parser.add_argument("--pilot-samples", type=int, default=2)
    parser.add_argument("--total-request-cap", type=int, default=24)
    parser.add_argument("--seeds", nargs="+", type=int, default=[20261122, 20261123])
    parser.add_argument(
        "--arms",
        nargs="+",
        default=["fixed_pointwise", "dev_fixed_strong", "short_pilot_racing", "diagnostic_rule_planner", "llm_diagnostic_planner"],
    )
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.budget_id):
        parser.error("invalid budget ID")
    allowed_arms = {"fixed_pointwise", "dev_fixed_strong", "short_pilot_racing",
                    "diagnostic_rule_planner", "llm_diagnostic_planner"}
    if set(args.arms) - allowed_arms or len(set(args.arms)) != len(args.arms) or len(set(args.seeds)) != len(args.seeds):
        parser.error("arms and seeds must be valid and unique")
    budget_outputs = (
        f"budget_probe_{args.budget_id}.json", f"workbench_bundle_{args.budget_id}",
        f"dashboard_{args.budget_id}", f"four_arm_report_{args.budget_id}.json",
    )
    if any((out_root / name).exists() for name in budget_outputs):
        parser.error("budget outputs already exist; use a fresh --out-root")
    (out_root / args.budget_id).mkdir(exist_ok=False)
    t_all0 = time.perf_counter()

    diag_json = _REPO / "experiments" / "milestone2" / "diagnostics" / "gap_decomposition_2x3.json"
    diag_doc = json.loads(diag_json.read_text(encoding="utf-8"))
    diag_ref = {
        "path": "experiments/milestone2/diagnostics/gap_decomposition_2x3.json",
        "sha256": hashlib.sha256(diag_json.read_bytes()).hexdigest(),
        "usage_role": "dev_selection",
    }

    budget_probe = probe_template_budget_headroom(
        time_budget_ms=args.target_budget_ms,
        probe_suite_specs=(("cvrp_dev_hetero_24", "dev_train", 24), ("cvrp_select_multiscale_64", "selection", 16)),
        include_n200_probe=True,
    )
    (out_root / f"budget_probe_{args.budget_id}.json").write_text(
        json.dumps(budget_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    jobs = [(arm, seed) for seed in args.seeds for arm in args.arms]
    run_outputs: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as pool:
        futs = [
            pool.submit(
                _run_seed_arm,
                arm,
                seed,
                out_root=out_root,
                budget_id=args.budget_id,
                target_budget_ms=args.target_budget_ms,
                total_samples=args.total_samples,
                pilot_samples=args.pilot_samples,
                total_request_cap=args.total_request_cap,
                strong_template_id=args.strong_template_id,
                endpoint=args.endpoint,
                model=args.model,
                api_key_env=args.api_key_env,
                diag_doc=diag_doc,
                diag_ref=diag_ref,
                budget_probe=budget_probe,
            )
            for arm, seed in jobs
        ]
        for fut in futs:
            run_outputs.append(fut.result())

    frozen_solvers = [FrozenInterfaceSolver.from_dict(r["frozen_solver"]) for r in run_outputs]
    bundle_dir = out_root / f"workbench_bundle_{args.budget_id}"
    dash_dir = out_root / f"dashboard_{args.budget_id}"
    wb = run_frozen_workbench_bundle(
        bundle_dir,
        frozen_solvers=frozen_solvers,
        reference_solver_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
        suite_specs=(
            ("cvrp_dev_hetero_24", "dev_train"),
            ("cvrp_select_multiscale_64", "selection"),
        ),
        budget_id=args.budget_id,
        time_budget_ms=args.target_budget_ms,
    )
    dash = build_dashboard(
        bundle_dir=bundle_dir,
        workspace_dir=_REPO / "knowledge_workspace",
        output_dir=dash_dir,
        release_id=f"m2-phase2b-four-arm-{args.budget_id}",
    )

    wb_sum = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    per_inst = json.loads((bundle_dir / "results" / "per_instance_records.json").read_text(encoding="utf-8"))["records"]

    archive = ComplementaryArchive(out_root / args.budget_id / "archive")
    detailed_runs: list[dict[str, Any]] = []
    for r in run_outputs:
        sid = r["frozen_solver"]["solver_id"]
        dev_m = wb_sum["suites"]["cvrp_dev_hetero_24"]["algorithms"][sid]["overall"]
        sel_m = wb_sum["suites"]["cvrp_select_multiscale_64"]["algorithms"][sid]["overall"]
        eoh_req = r["eoh_requests"]
        tot_req = int(r["planning_requests"]) + int(eoh_req.get("completed_requests", 0))
        tot_attempts = int(r.get("planning_request_attempts", r["planning_requests"])) + int(
            eoh_req.get("attempted_requests", eoh_req.get("completed_requests", 0))
        )
        tot_in = int(r["planning_input_tokens"]) + int(eoh_req.get("prompt_tokens", 0))
        tot_out = int(r["planning_output_tokens"]) + int(eoh_req.get("completion_tokens", 0))
        row = {
            "arm_id": r["arm_id"],
            "seed": r["seed"],
            "solver_id": sid,
            "selected_template_id": r["selected_template_id"],
            "total_requests": tot_req,
            "total_request_attempts": tot_attempts,
            "planning_requests": r["planning_requests"],
            "total_input_tokens": tot_in,
            "total_output_tokens": tot_out,
            "total_tokens": tot_in + tot_out,
            "diagnostic_probe_wall_ms": r["diagnostic_probe_wall_ms"],
            "wall_s": r["wall_s"],
            "dev_24_mean": dev_m["mean_tour_length"],
            "dev_24_completion": dev_m["completion_rate"],
            "select_64_mean": sel_m["mean_tour_length"],
            "select_64_completion": sel_m["completion_rate"],
            "select_64_budget_exhausted_ok": sel_m["ok_budget_exhausted_count"],
            "select_64_solve_ms_p50": sel_m["solve_ms_p50"],
            "select_64_solve_ms_p95": sel_m["solve_ms_p95"],
        }
        detailed_runs.append(row)
        archive.register(
            r["frozen_solver"],
            arm_id=r["arm_id"],
            search_seed=r["seed"],
            budget_id=args.budget_id,
            suite_metrics={"dev_24": dev_m, "select_64": sel_m},
            resource_ledger=row,
        )

    # Aggregate paired-seed summary by arm
    arm_summary: dict[str, Any] = {}
    for arm in args.arms:
        rows = [x for x in detailed_runs if x["arm_id"] == arm]
        arm_summary[arm] = {
            "n_seeds": len(rows),
            "selected_templates": [x["selected_template_id"] for x in rows],
            "dev_24_mean_avg": round(float(np.mean([x["dev_24_mean"] for x in rows if x["dev_24_mean"] is not None])), 4),
            "select_64_mean_avg": round(float(np.mean([x["select_64_mean"] for x in rows if x["select_64_mean"] is not None])), 4),
            "select_64_best": round(float(min(x["select_64_mean"] for x in rows if x["select_64_mean"] is not None)), 4),
            "select_64_completion_avg": round(float(np.mean([x["select_64_completion"] for x in rows])), 4),
            "select_64_solve_ms_p50_avg": round(float(np.mean([x["select_64_solve_ms_p50"] for x in rows])), 4),
            "total_requests_avg": round(float(np.mean([x["total_requests"] for x in rows])), 2),
            "total_request_attempts_avg": round(float(np.mean([x["total_request_attempts"] for x in rows])), 2),
            "total_tokens_avg": round(float(np.mean([x["total_tokens"] for x in rows])), 1),
            "wall_s_avg": round(float(np.mean([x["wall_s"] for x in rows])), 2),
        }

    comp_sel64 = compute_portfolio_complementarity(
        per_inst,
        suite_id="cvrp_select_multiscale_64",
        solver_ids=["s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge", *[r["solver_id"] for r in detailed_runs]],
    )

    report = {
        "schema_version": "m2-phase2b-four-arm-report/v1",
        "budget_id": args.budget_id,
        "target_budget_ms": args.target_budget_ms,
        "model": args.model,
        "config": {
            "total_samples": args.total_samples,
            "pilot_samples": args.pilot_samples,
            "total_request_cap": args.total_request_cap,
            "strong_template_id": args.strong_template_id,
            "seeds": args.seeds,
            "arms": args.arms,
        },
        "budget_probe_templates": budget_probe["templates"],
        "reference_baselines": {
            sid: {
                aid: wb_sum["suites"][sid]["algorithms"][aid]["overall"]
                for aid in ("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge")
            }
            for sid in ("cvrp_dev_hetero_24", "cvrp_select_multiscale_64")
        },
        "arm_summary": arm_summary,
        "runs": detailed_runs,
        "complementarity_select_64": comp_sel64,
        "dashboard_html": dash["dashboard_html"],
        "total_wall_s": round(time.perf_counter() - t_all0, 2),
    }
    report_path = out_root / f"four_arm_report_{args.budget_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
