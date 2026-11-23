"""Milestone 3 Phase 3C Runner: Paired Multi-Seed Four-Arm Fair-Budget Comparison + Backbone Attribution.

Runs all 4 experimental arms under identical shared PersistentRequestBudget (B_total=36),
same underlying model (deepseek-v4.1-flash via OpenCode Go), dev-only interactive visibility
(cvrp_dev_hetero_24), zero static KB clue injection, and strict 5-gate validation:

  - arm_m3_0_pure_eoh      : 0 outer requests, agent_guidance=False, locked {L2a} (none), 100% EoH
  - arm_m3_1_plain_text    : plain-text reflection baseline (PyVRP+/ReEvo style), locked {L2a} (none), no tools/sandbox
  - arm_m3_2_fixed_l2a     : full Research Agent (KB + slice + sandbox + ledger + Archive), locked {L2a} + all postprocess
  - arm_m3_3_full_dynamic  : identical to M3-2 except full template choice {L1, L2a, L2b, L3}

Supports both standard_500ms (all 3 seeds: 20261124, 20261125, 20261126) and tight_25ms,
crash-safe per-(budget, seed, arm) resume, post-search offline evaluation on cvrp_dev_hetero_24 +
cvrp_select_multiscale_64, and Section 5.3 zero-LLM controlled backbone & anytime ablation.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.client import load_local_env
from agent_skill_loop.cvrp_workbench.runner import aggregate_records, evaluate_algorithm_on_instance, run_frozen_workbench_bundle
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.archive import ComplementaryArchive
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.templates import build_ruin_recreate_design, get_template_spec
from agent_skill_loop.request_budget import PersistentRequestBudget
from research_agent import AgentConfig, run_research_agent

DEFAULT_SEEDS: tuple[int, ...] = (20261124, 20261125, 20261126)
DEFAULT_ARMS: tuple[str, ...] = (
    "arm_m3_0_pure_eoh",
    "arm_m3_1_plain_text",
    "arm_m3_2_fixed_l2a",
    "arm_m3_3_full_dynamic",
)


def build_arm_config(
    *,
    arm_id: str,
    seed: int,
    budget_id: str,
    target_budget_ms: float,
    total_request_cap: int,
    out_dir: Path,
    endpoint: str,
    model: str,
    api_key_env: str,
    mode: str = "live",
) -> AgentConfig:
    run_id = f"m3_3c_{budget_id}_{arm_id}_s{seed}"
    common = dict(
        run_id=run_id,
        output_dir=str(out_dir),
        arm_id=arm_id,
        max_rounds=3,
        total_request_cap=total_request_cap,
        instance_time_budget_ms=float(target_budget_ms),
        planner_model=model,
        eoh_model=model,
        endpoint=endpoint,
        api_key_env=api_key_env,
        search_seed=seed,
        use_benchmark_dev_suite=True,
        eval_dev_suite=True,
        inject_static_kb_clues=False,
        checkpoint_budgets=(18, total_request_cap),
        mode=mode,
        request_timeout_s=90.0,
        wall_seconds=900.0,
    )
    if arm_id == "arm_m3_0_pure_eoh":
        return AgentConfig(
            **common,
            outer_requests_per_round_cap=0,
            outer_reflect_cap=0,
            eoh_pop_size=3,
            eoh_n_pop=2,
            eoh_max_sample_nums=11,
            agent_guidance=False,
            tools_enabled=False,
            archive_feedback_enabled=False,
            allowed_templates=("cvrp_parallel_merge_static",),
            allowed_postprocess_modes=("none",),
            initial_template_id="cvrp_parallel_merge_static",
            initial_postprocess_mode="none",
        )
    if arm_id == "arm_m3_1_plain_text":
        return AgentConfig(
            **common,
            outer_requests_per_round_cap=1,
            outer_reflect_cap=1,
            eoh_pop_size=3,
            eoh_n_pop=2,
            eoh_max_sample_nums=9,
            agent_guidance=True,
            tools_enabled=False,
            archive_feedback_enabled=False,
            allowed_templates=("cvrp_parallel_merge_static",),
            allowed_postprocess_modes=("none",),
            initial_template_id="cvrp_parallel_merge_static",
            initial_postprocess_mode="none",
        )
    if arm_id == "arm_m3_2_fixed_l2a":
        return AgentConfig(
            **common,
            outer_requests_per_round_cap=4,
            outer_reflect_cap=2,
            eoh_pop_size=2,
            eoh_n_pop=2,
            eoh_max_sample_nums=7,
            agent_guidance=True,
            tools_enabled=True,
            archive_feedback_enabled=True,
            allowed_templates=("cvrp_parallel_merge_static",),
            allowed_postprocess_modes=("none", "intra_2opt", "relocate_2opt"),
            initial_template_id="cvrp_parallel_merge_static",
            initial_postprocess_mode="none",
        )
    if arm_id == "arm_m3_3_full_dynamic":
        return AgentConfig(
            **common,
            outer_requests_per_round_cap=4,
            outer_reflect_cap=2,
            eoh_pop_size=2,
            eoh_n_pop=2,
            eoh_max_sample_nums=7,
            agent_guidance=True,
            tools_enabled=True,
            archive_feedback_enabled=True,
            allowed_templates=(
                "cvrp_sequential_construct",
                "cvrp_parallel_merge_static",
                "cvrp_parallel_merge_dynamic",
                "cvrp_ruin_recreate",
            ),
            allowed_postprocess_modes=("none", "intra_2opt", "relocate_2opt"),
            initial_template_id="cvrp_parallel_merge_static",
            initial_postprocess_mode="none",
        )
    raise ValueError(f"unknown_arm_id:{arm_id}")


def _run_one_job(
    arm_id: str,
    seed: int,
    *,
    out_root: Path,
    budget_id: str,
    target_budget_ms: float,
    total_request_cap: int,
    endpoint: str,
    model: str,
    api_key_env: str,
    mode: str,
) -> dict[str, Any]:
    load_local_env()
    arm_dir = out_root / budget_id / f"seed_{seed}" / arm_id
    summary_path = arm_dir / "research_summary.json"
    ckpt_path = arm_dir / "agent_checkpoint.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return {"ok": True, "resumed": True, "already_done": True, "arm_id": arm_id, "seed": seed, "summary": summary, "arm_dir": str(arm_dir)}

    cfg = build_arm_config(
        arm_id=arm_id,
        seed=seed,
        budget_id=budget_id,
        target_budget_ms=target_budget_ms,
        total_request_cap=total_request_cap,
        out_dir=arm_dir,
        endpoint=endpoint,
        model=model,
        api_key_env=api_key_env,
        mode=mode,
    )
    t0 = time.perf_counter()
    resume = ckpt_path.is_file()
    summary: dict[str, Any] | None = None
    for outer_try in range(3):
        try:
            summary = run_research_agent(cfg, resume=resume)
            break
        except Exception as exc:
            if "ProviderFailure" in type(exc).__name__ or "provider_connectivity" in str(exc) or "request_deadline" in str(exc):
                if ckpt_path.is_file() and outer_try < 2:
                    time.sleep(25.0)
                    resume = True
                    continue
            raise
    assert summary is not None
    return {
        "ok": True,
        "resumed": resume,
        "already_done": False,
        "wall_s": round(time.perf_counter() - t0, 2),
        "arm_id": arm_id,
        "seed": seed,
        "summary": summary,
        "arm_dir": str(arm_dir),
    }


def _build_l3_ctrl_solver(budget_ms: float) -> FrozenInterfaceSolver:
    design = build_ruin_recreate_design(design_id="m3_l3_ctrl_worst_removal")
    tpl = get_template_spec(design.template_id, design.template_version)
    return FrozenInterfaceSolver(
        solver_id=f"m3_l3_ctrl_{int(budget_ms)}ms",
        display_name=f"M3 L3-ctrl Worst Removal ({int(budget_ms)}ms)",
        problem_family="cvrp",
        paradigm=design.paradigm,
        template_id=design.template_id,
        template_version=design.template_version,
        template_source_sha256=tpl.template_source_sha256,
        postprocess_mode=design.postprocess_mode,
        template_options=dict(design.template_options),
        hook_name=design.hook_name,
        hook_code=design.baseline_hook_code,
        hook_code_sha256=sha256_text(design.baseline_hook_code),
        design_sha256=design.design_sha256,
        origin_run="m3_3c_controlled_baseline",
        kb_release_id="20261123-main-co-workbench-m2",
        kb_entry_id=None,
        cited_kb_ids=(),
        diagnostic_ref=None,
        description="Controlled L3 Worst-Cost Removal baseline (separates LNS skeleton from evolved ruin scoring).",
        default_budget_ms=float(budget_ms),
    )


def _eval_and_archive_budget(
    *,
    out_root: Path,
    budget_id: str,
    target_budget_ms: float,
    arms: Sequence[str],
    seeds: Sequence[int],
    job_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    archive = ComplementaryArchive(out_root / "archive")
    representative_solvers: list[FrozenInterfaceSolver] = []
    run_rows: list[dict[str, Any]] = []

    for jr in job_results:
        arm_id = str(jr["arm_id"])
        seed = int(jr["seed"])
        arm_dir = Path(str(jr["arm_dir"]))
        summ = jr["summary"]
        best_ref = summ.get("best_solver_manifest_ref")
        if not best_ref or not (arm_dir / best_ref).is_file():
            raise RuntimeError(f"missing_best_solver_manifest:{arm_dir}")
        raw_solver = json.loads((arm_dir / best_ref).read_text(encoding="utf-8"))
        raw_solver["solver_id"] = f"m3_3c_{budget_id}_{arm_id}_s{seed}"
        raw_solver["display_name"] = f"M3 {arm_id} (s{seed}, {int(target_budget_ms)}ms)"
        fs = FrozenInterfaceSolver.from_dict(raw_solver)
        representative_solvers.append(fs)

        round_templates = [r.get("template_id") for r in summ.get("round_summaries", [])]
        round_pps = [r.get("postprocess_mode") for r in summ.get("round_summaries", [])]
        bs = summ["budget_summary"]
        ts = summ.get("token_summary") or {}
        run_rows.append({
            "budget_id": budget_id,
            "target_budget_ms": target_budget_ms,
            "arm_id": arm_id,
            "seed": seed,
            "solver_id": fs.solver_id,
            "selected_template_id": fs.template_id,
            "selected_postprocess_mode": fs.postprocess_mode,
            "round_templates": round_templates,
            "round_postprocess_modes": round_pps,
            "dev_24_penalized_mean": summ.get("best_dev_objective"),
            "attempted_requests": bs.get("attempted_requests"),
            "completed_requests": (bs.get("by_state") or {}).get("complete", 0),
            "rejected_requests": bs.get("rejected_requests"),
            "reconciled_unknown_count": bs.get("reconciled_unknown_count"),
            "input_tokens": ts.get("input_tokens", bs.get("input_tokens", 0)),
            "output_tokens": ts.get("output_tokens", bs.get("output_tokens", 0)),
            "total_tokens": ts.get("total_tokens", bs.get("total_tokens", 0)),
            "outer_requests": ts.get("outer_requests", 0),
            "inner_eoh_requests": ts.get("inner_eoh_requests", 0),
            "provider_elapsed_seconds": ts.get("provider_elapsed_seconds", 0.0),
        })

    # Include L3-ctrl controlled baseline cleanly for standard_500ms & tight_25ms
    l3_ctrl = _build_l3_ctrl_solver(target_budget_ms)
    all_frozen = [*representative_solvers, l3_ctrl]

    bundle_dir = out_root / f"workbench_bundle_{budget_id}"
    if bundle_dir.exists():
        import shutil
        shutil.rmtree(bundle_dir)
    wb_res = run_frozen_workbench_bundle(
        bundle_dir,
        frozen_solvers=all_frozen,
        reference_solver_ids=("cw_parallel_merge", "cw_relocate_2opt", "s2_r5_spiral", "i605_cvrp_c1_tworegime"),
        suite_specs=(("cvrp_dev_hetero_24", "dev_train"), ("cvrp_select_multiscale_64", "selection")),
        budget_id=budget_id,
        time_budget_ms=target_budget_ms,
    )
    wb_sum = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))

    for r in run_rows:
        sid = r["solver_id"]
        d24 = wb_sum["suites"]["cvrp_dev_hetero_24"]["algorithms"][sid]["overall"]
        s64 = wb_sum["suites"]["cvrp_select_multiscale_64"]["algorithms"][sid]["overall"]
        r["dev_24_mean"] = d24["mean_tour_length"]
        r["dev_24_completion_rate"] = d24["completion_rate"]
        r["dev_24_solve_ms_p50"] = d24["solve_ms_p50"]
        r["select_64_mean"] = s64["mean_tour_length"]
        r["select_64_completion_rate"] = s64["completion_rate"]
        r["select_64_budget_exhausted_count"] = s64["budget_exhausted_count"]
        r["select_64_solve_ms_p50"] = s64["solve_ms_p50"]
        r["select_64_solve_ms_p95"] = s64["solve_ms_p95"]

    for fs in all_frozen:
        sid = fs.solver_id
        s64 = wb_sum["suites"]["cvrp_select_multiscale_64"]["algorithms"][sid]["overall"]
        d24 = wb_sum["suites"]["cvrp_dev_hetero_24"]["algorithms"][sid]["overall"]
        row_match = next((r for r in run_rows if r["solver_id"] == sid), None)
        archive.register(
            fs,
            arm_id=row_match["arm_id"] if row_match else "l3_ctrl_baseline",
            search_seed=row_match["seed"] if row_match else None,
            budget_id=budget_id,
            suite_metrics={
                "cvrp_dev_hetero_24": d24,
                "cvrp_select_multiscale_64": s64,
                "mean_tour_length": s64["mean_tour_length"],
                "solve_ms_mean": s64["solve_ms_mean"],
            },
            resource_ledger=row_match or {},
        )

    arm_summary: dict[str, Any] = {}
    for arm_id in arms:
        rows = [r for r in run_rows if r["arm_id"] == arm_id]
        if not rows:
            continue
        arm_summary[arm_id] = {
            "n_seeds": len(rows),
            "seeds": [r["seed"] for r in rows],
            "selected_templates": [r["selected_template_id"] for r in rows],
            "selected_postprocess_modes": [r["selected_postprocess_mode"] for r in rows],
            "select_64_means": [r["select_64_mean"] for r in rows],
            "select_64_mean_avg": round(sum(float(r["select_64_mean"]) for r in rows) / len(rows), 4),
            "select_64_best": min(float(r["select_64_mean"]) for r in rows),
            "select_64_completion_avg": round(sum(float(r["select_64_completion_rate"]) for r in rows) / len(rows), 4),
            "attempted_requests_avg": round(sum(float(r["attempted_requests"]) for r in rows) / len(rows), 2),
            "completed_requests_avg": round(sum(float(r["completed_requests"]) for r in rows) / len(rows), 2),
            "total_tokens_avg": round(sum(float(r["total_tokens"]) for r in rows) / len(rows), 1),
        }

    report = {
        "schema_version": "m3-phase3c-four-arm-report/v1",
        "budget_id": budget_id,
        "target_budget_ms": target_budget_ms,
        "l3_ctrl_select_64": wb_sum["suites"]["cvrp_select_multiscale_64"]["algorithms"][l3_ctrl.solver_id]["overall"],
        "reference_baselines_select_64": {
            aid: wb_sum["suites"]["cvrp_select_multiscale_64"]["algorithms"][aid]["overall"]
            for aid in ("cw_parallel_merge", "cw_relocate_2opt", "s2_r5_spiral", "i605_cvrp_c1_tworegime")
        },
        "arm_summary": arm_summary,
        "runs": run_rows,
        "workbench_bundle": wb_res,
    }
    report_path = out_root / f"phase3c_report_{budget_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def run_backbone_and_anytime_attribution(out_root: Path, report_500: Mapping[str, Any]) -> dict[str, Any]:
    """Section 5.3 zero-LLM controlled backbone & anytime trajectory comparison on cvrp_select_multiscale_64."""
    suite64 = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    archive_manifest = json.loads((out_root / "archive" / "archive_manifest.json").read_text(encoding="utf-8"))
    by_id = {row["solver_id"]: FrozenInterfaceSolver.from_dict(row["frozen_solver"]) for row in archive_manifest["solvers"]}

    best_l2a_run = min(report_500["runs"], key=lambda r: (0 if r["selected_template_id"] == "cvrp_parallel_merge_static" else 1, float(r["select_64_mean"])))
    l3_runs = [r for r in report_500["runs"] if r["selected_template_id"] == "cvrp_ruin_recreate"]
    target_solvers: list[tuple[str, FrozenInterfaceSolver | None]] = [
        ("best_l2a", by_id[best_l2a_run["solver_id"]]),
        ("l3_ctrl", by_id["m3_l3_ctrl_500ms"]),
    ]
    if l3_runs:
        best_l3_run = min(l3_runs, key=lambda r: float(r["select_64_mean"]))
        target_solvers.append(("best_l3_evolved", by_id[best_l3_run["solver_id"]]))

    anytime_summary: dict[str, Any] = {}
    for label, fs in target_solvers:
        assert fs is not None
        recs = [
            evaluate_frozen_interface_solver(
                fs,
                inst,
                distance_convention=suite64["distance_convention"],
                vehicle_limit_policy=suite64["vehicle_limit_policy"],
                time_budget_ms=500.0,
            )
            for inst in suite64["instances"]
        ]
        valid = [r for r in recs if r.get("valid") and r.get("tour_length") is not None]
        anytime_points = ("10", "25", "100", "250", "500")
        curve_agg: dict[str, float | None] = {}
        for cp in anytime_points:
            vals = [float((r.get("anytime_curve") or {}).get(cp)) for r in valid if isinstance((r.get("anytime_curve") or {}).get(cp), (int, float))]
            curve_agg[cp] = round(sum(vals) / len(vals), 4) if len(vals) == len(valid) and valid else None
        first_feas = [float(r["first_feasible_ms"]) for r in valid if r.get("first_feasible_ms") is not None]
        anytime_summary[label] = {
            "solver_id": fs.solver_id,
            "template_id": fs.template_id,
            "postprocess_mode": fs.postprocess_mode,
            "mean_tour_length": round(sum(float(r["tour_length"]) for r in valid) / len(valid), 4) if valid else None,
            "valid_count": len(valid),
            "first_feasible_ms_mean": round(sum(first_feas) / len(first_feas), 4) if first_feas else None,
            "anytime_curve_means": curve_agg,
        }

    # Include CW + Relocate+2opt baseline cleanly
    cw_recs = [
        evaluate_algorithm_on_instance(
            "cw_relocate_2opt",
            inst,
            distance_convention=suite64["distance_convention"],
            vehicle_limit_policy=suite64["vehicle_limit_policy"],
            time_budget_ms=500.0,
            record_trace=False,
        )
        for inst in suite64["instances"]
    ]
    cw_valid = [float(r["tour_length"]) for r in cw_recs if r.get("valid") and r.get("tour_length") is not None]
    anytime_summary["cw_relocate_2opt"] = {
        "solver_id": "cw_relocate_2opt",
        "mean_tour_length": round(sum(cw_valid) / len(cw_valid), 4),
        "valid_count": len(cw_valid),
    }
    out = {
        "schema_version": "m3-backbone-attribution/v1",
        "suite_id": "cvrp_select_multiscale_64",
        "comparisons": anytime_summary,
    }
    (out_root / "backbone_attribution_report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=_REPO / "experiments" / "milestone3" / "phase3c_four_arm")
    parser.add_argument("--budget-id", default="standard_500ms")
    parser.add_argument("--target-budget-ms", type=float, default=500.0)
    parser.add_argument("--total-request-cap", type=int, default=36)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--arms", nargs="+", default=list(DEFAULT_ARMS))
    parser.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    parser.add_argument("--model", default="deepseek-v4.1-flash")
    parser.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    parser.add_argument("--mode", choices=("live", "mock"), default="live")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    jobs = [(arm, seed) for seed in args.seeds for arm in args.arms]
    results: list[dict[str, Any]] = []
    if args.workers <= 1:
        for arm, seed in jobs:
            print(f"[3C] Running {args.budget_id} | seed={seed} | {arm} ...", flush=True)
            res = _run_one_job(
                arm,
                seed,
                out_root=out_root,
                budget_id=args.budget_id,
                target_budget_ms=args.target_budget_ms,
                total_request_cap=args.total_request_cap,
                endpoint=args.endpoint,
                model=args.model,
                api_key_env=args.api_key_env,
                mode=args.mode,
            )
            results.append(res)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futs = [
                pool.submit(
                    _run_one_job,
                    arm,
                    seed,
                    out_root=out_root,
                    budget_id=args.budget_id,
                    target_budget_ms=args.target_budget_ms,
                    total_request_cap=args.total_request_cap,
                    endpoint=args.endpoint,
                    model=args.model,
                    api_key_env=args.api_key_env,
                    mode=args.mode,
                )
                for arm, seed in jobs
            ]
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())

    report = _eval_and_archive_budget(
        out_root=out_root,
        budget_id=args.budget_id,
        target_budget_ms=args.target_budget_ms,
        arms=args.arms,
        seeds=args.seeds,
        job_results=results,
    )
    if args.budget_id == "standard_500ms":
        run_backbone_and_anytime_attribution(out_root, report)
    print(json.dumps(report["arm_summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
