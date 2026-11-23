"""Phase 2B Step 1: Controlled 3-way Static (L2a) vs Refresh+Static (L2b-ctrl) vs Dynamic-State (L2b) Attribution.

Using deepseek-v4.1-flash (OpenCode Go) under identical EoH budget, compares:
  1. L2a baseline (raw CW static savings)
  2. L2b-ctrl (dynamic candidate refresh + static CW savings -> isolates pure refresh overhead)
  3. L2a evolved (static merge priority evolved by EoH)
  4. L2b evolved (dynamic state-feedback merge priority evolved by EoH)

Exports BOTH a standard 500 ms Workbench bundle (+ dashboard) and a tight 25 ms Workbench bundle
(+ dashboard) to measure quality-vs-latency & budget-headroom discrimination cleanly.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from agent_skill_loop.cvrp_workbench.runner import run_frozen_workbench_bundle
from agent_skill_loop.interface_design.archive import ComplementaryArchive, compute_portfolio_complementarity
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.dynamic_eoh import run_dynamic_eoh_evolution
from agent_skill_loop.interface_design.planner import KB_ROUND_CONTEXT_BY_TEMPLATE, probe_template_budget_headroom
from agent_skill_loop.interface_design.templates import (
    CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
    build_classic_cw_static_design,
    build_parallel_merge_dynamic_design,
    get_template_spec,
)
from frontend.build_dashboard import build_dashboard


def _evolve_arm(
    arm_kind: str,
    *,
    out_root: Path,
    endpoint: str,
    model: str,
    api_key_env: str,
    pop_size: int,
    n_pop: int,
    max_sample_nums: int,
    max_requests: int,
    search_seed: int,
    diagnostic_ref: dict[str, Any] | None,
) -> dict[str, Any]:
    if arm_kind == "l2a":
        design = build_classic_cw_static_design(
            design_id=f"m2_2b_attr_l2a_seed{search_seed}",
            postprocess_mode="none",
            diagnostic_ref=diagnostic_ref,
        )
        solver_id = f"m2_2b_l2a_evolved_s{search_seed}"
        display_name = f"M2 L2a Static Evolved (seed {search_seed})"
    elif arm_kind == "l2b":
        design = build_parallel_merge_dynamic_design(
            design_id=f"m2_2b_attr_l2b_seed{search_seed}",
            postprocess_mode="none",
            diagnostic_ref=diagnostic_ref,
        )
        solver_id = f"m2_2b_l2b_evolved_s{search_seed}"
        display_name = f"M2 L2b Dynamic State Evolved (seed {search_seed})"
    else:
        raise ValueError(f"unknown_arm_kind:{arm_kind}")

    run_dir = out_root / f"eoh_{arm_kind}_seed{search_seed}"
    res = run_dynamic_eoh_evolution(
        design=design,
        output_dir=run_dir,
        suite_id="cvrp_dev_hetero_24",
        split="dev_train",
        pop_size=pop_size,
        n_pop=n_pop,
        max_sample_nums=max_sample_nums,
        operators=("e1", "e2", "m1", "m2"),
        search_seed=search_seed,
        solver_id=solver_id,
        display_name=display_name,
        mode="live",
        endpoint=endpoint,
        model=model,
        api_key_env=api_key_env,
        max_requests=max_requests,
        request_timeout_s=120.0,
        wall_seconds=420.0,
        require_evolved=True,
        round_context=KB_ROUND_CONTEXT_BY_TEMPLATE.get(design.template_id),
    )
    return {"arm_kind": arm_kind, **res}


def _build_l2b_ctrl_frozen(diagnostic_ref: dict[str, Any] | None) -> FrozenInterfaceSolver:
    design = build_parallel_merge_dynamic_design(
        design_id="m2_2b_l2b_ctrl_refresh_static",
        postprocess_mode="none",
        diagnostic_ref=diagnostic_ref,
    )
    tpl = get_template_spec("cvrp_parallel_merge_dynamic", "v1")
    return FrozenInterfaceSolver(
        solver_id="m2_2b_l2b_ctrl_static_refresh",
        display_name="M2 L2b-ctrl · Dynamic Refresh + Static CW",
        problem_family="cvrp",
        paradigm="parallel_merge",
        template_id=tpl.template_id,
        template_version=tpl.template_version,
        template_source_sha256=tpl.template_source_sha256,
        postprocess_mode="none",
        template_options={"positive_savings_only": True},
        hook_name=tpl.hook_name,
        hook_code=CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE,
        hook_code_sha256=sha256_text(CLASSIC_CW_DYNAMIC_STATIC_HOOK_CODE),
        design_sha256=design.design_sha256,
        origin_run="control_l2b_refresh_static_cw",
        kb_release_id="20261122-main-co-workbench-m15",
        kb_entry_id="method-cvrp-cw-parallel",
        cited_kb_ids=("method-cvrp-cw-parallel",),
        diagnostic_ref=diagnostic_ref,
        description="Controlled ablation: dynamic candidate refresh after every merge with pure static CW savings.",
        default_budget_ms=500.0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=_REPO / "experiments" / "milestone2" / "phase2b_l2_attribution")
    parser.add_argument("--endpoint", default="https://opencode.ai/zen/go/v1/chat/completions")
    parser.add_argument("--model", default="deepseek-v4.1-flash")
    parser.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    parser.add_argument("--pop-size", type=int, default=4)
    parser.add_argument("--n-pop", type=int, default=4)
    parser.add_argument("--max-sample-nums", type=int, default=16)
    parser.add_argument("--max-requests", type=int, default=28)
    parser.add_argument("--search-seed", type=int, default=20261122)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if any(out_root.iterdir()):
        parser.error("--out-root must be a fresh experiment directory")
    with (out_root / "attribution.started").open("x", encoding="utf-8"):
        pass
    t0 = time.perf_counter()

    diag_json = _REPO / "experiments" / "milestone2" / "diagnostics" / "gap_decomposition_2x3.json"
    diag_ref = {
        "path": "experiments/milestone2/diagnostics/gap_decomposition_2x3.json",
        "sha256": hashlib.sha256(diag_json.read_bytes()).hexdigest(),
        "usage_role": "dev_selection",
    }

    # 1. Zero-token timing & headroom probes under 500 ms AND 25 ms
    probe_500 = probe_template_budget_headroom(
        time_budget_ms=500.0,
        probe_suite_specs=(("cvrp_dev_hetero_24", "dev_train", 24), ("cvrp_select_multiscale_64", "selection", 16)),
        include_n200_probe=True,
    )
    probe_25 = probe_template_budget_headroom(
        time_budget_ms=25.0,
        probe_suite_specs=(("cvrp_dev_hetero_24", "dev_train", 24), ("cvrp_select_multiscale_64", "selection", 16)),
        include_n200_probe=True,
    )
    (out_root / "budget_probe_500ms.json").write_text(json.dumps(probe_500, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_root / "budget_probe_25ms.json").write_text(json.dumps(probe_25, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 2. Run L2a & L2b EoH evolution in isolated processes under identical budget
    evo_results: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, min(args.workers, 2))) as pool:
        futs = [
            pool.submit(
                _evolve_arm,
                kind,
                out_root=out_root,
                endpoint=args.endpoint,
                model=args.model,
                api_key_env=args.api_key_env,
                pop_size=args.pop_size,
                n_pop=args.n_pop,
                max_sample_nums=args.max_sample_nums,
                max_requests=args.max_requests,
                search_seed=args.search_seed,
                diagnostic_ref=diag_ref,
            )
            for kind in ("l2a", "l2b")
        ]
        for fut in futs:
            r = fut.result()
            evo_results[r["arm_kind"]] = r

    l2b_ctrl = _build_l2b_ctrl_frozen(diag_ref)
    l2a_fs = FrozenInterfaceSolver.from_dict(evo_results["l2a"]["frozen_solver"])
    l2b_fs = FrozenInterfaceSolver.from_dict(evo_results["l2b"]["frozen_solver"])
    frozen_list = [l2b_ctrl, l2a_fs, l2b_fs]

    # 3. Evaluate on BOTH 500 ms and 25 ms Workbench bundles + dashboards
    budget_summaries: dict[str, Any] = {}
    for budget_id, budget_ms in (("standard_500ms", 500.0), ("tight_25ms", 25.0)):
        b_dir = out_root / f"workbench_bundle_{budget_id}"
        d_dir = out_root / f"dashboard_{budget_id}"
        wb = run_frozen_workbench_bundle(
            b_dir,
            frozen_solvers=frozen_list,
            reference_solver_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
            suite_specs=(
                ("cvrp_dev_hetero_24", "dev_train"),
                ("cvrp_select_multiscale_64", "selection"),
            ),
            budget_id=budget_id,
            time_budget_ms=budget_ms,
        )
        dash = build_dashboard(
            bundle_dir=b_dir,
            workspace_dir=_REPO / "knowledge_workspace",
            output_dir=d_dir,
            release_id=f"m2-phase2b-l2-attr-{budget_id}",
        )
        wb_sum = json.loads((b_dir / "results" / "summary.json").read_text(encoding="utf-8"))
        per_inst = json.loads((b_dir / "results" / "per_instance_records.json").read_text(encoding="utf-8"))["records"]
        comp_sel64 = compute_portfolio_complementarity(
            per_inst,
            suite_id="cvrp_select_multiscale_64",
            solver_ids=["s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge", l2a_fs.solver_id, l2b_fs.solver_id],
        )
        budget_summaries[budget_id] = {
            "budget_ms": budget_ms,
            "workbench": wb,
            "dashboard_html": dash["dashboard_html"],
            "suites": {
                sid: {
                    aid: {
                        "mean_tour_length": sdata["algorithms"][aid]["overall"]["mean_tour_length"],
                        "completion_rate": sdata["algorithms"][aid]["overall"]["completion_rate"],
                        "ok_budget_exhausted_count": sdata["algorithms"][aid]["overall"]["ok_budget_exhausted_count"],
                        "solve_ms_p50": sdata["algorithms"][aid]["overall"]["solve_ms_p50"],
                        "solve_ms_p95": sdata["algorithms"][aid]["overall"]["solve_ms_p95"],
                    }
                    for aid in sdata["algorithms"]
                }
                for sid, sdata in wb_sum["suites"].items()
            },
            "complementarity_select_64": comp_sel64,
        }

    # Register in ComplementaryArchive
    archive = ComplementaryArchive(out_root / "archive")
    for arm_name, fs, evo_key in (("l2b_ctrl", l2b_ctrl, None), ("l2a_evolved", l2a_fs, "l2a"), ("l2b_evolved", l2b_fs, "l2b")):
        archive.register(
            fs,
            arm_id=arm_name,
            search_seed=args.search_seed if evo_key else None,
            budget_id="standard_500ms",
            suite_metrics={
                "500ms_dev24": budget_summaries["standard_500ms"]["suites"]["cvrp_dev_hetero_24"][fs.solver_id],
                "500ms_sel64": budget_summaries["standard_500ms"]["suites"]["cvrp_select_multiscale_64"][fs.solver_id],
                "25ms_sel64": budget_summaries["tight_25ms"]["suites"]["cvrp_select_multiscale_64"][fs.solver_id],
            },
            resource_ledger=evo_results[evo_key]["resource_ledger"] if evo_key else {"mode": "baseline_control"},
        )

    report = {
        "schema_version": "m2-phase2b-l2-attribution/v1",
        "model": args.model,
        "search_seed": args.search_seed,
        "eoh_config": {
            "pop_size": args.pop_size,
            "n_pop": args.n_pop,
            "max_sample_nums": args.max_sample_nums,
            "max_requests": args.max_requests,
            "operators": ["e1", "e2", "m1", "m2"],
        },
        "budget_probes": {
            "500ms": probe_500["templates"],
            "25ms": probe_25["templates"],
        },
        "evolution_ledgers": {
            "l2a": evo_results["l2a"]["resource_ledger"],
            "l2b": evo_results["l2b"]["resource_ledger"],
        },
        "budgets": budget_summaries,
        "total_wall_s": round(time.perf_counter() - t0, 2),
    }
    report_path = out_root / "l2_attribution_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
