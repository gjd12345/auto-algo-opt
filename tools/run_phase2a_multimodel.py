"""Fair multi-model OpenCode Go comparison on Phase 2A (cvrp_parallel_merge_static/v1).

Runs each specified model under identical EoH budget, operators, search seed, and
5-gate validation, then puts all valid frozen winners + M1 references (R5, C1, CW)
into a single unified standard-500ms Workbench bundle and builds dashboard.html.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from agent_skill_loop.cvrp_workbench.runner import run_frozen_workbench_bundle
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.dynamic_eoh import run_dynamic_eoh_evolution
from agent_skill_loop.interface_design.templates import build_classic_cw_static_design
from frontend.build_dashboard import build_dashboard

DEFAULT_MODELS: tuple[str, ...] = (
    "deepseek-v4.1-flash",
    "deepseek-v4-pro",
    "kimi-k2.7-code",
    "glm-5.3",
    "qwen4-max",
)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _run_one_model(
    model: str,
    *,
    out_root: Path,
    endpoint: str,
    api_key_env: str,
    pop_size: int,
    n_pop: int,
    max_sample_nums: int,
    max_requests: int,
    search_seed: int,
    diagnostic_ref: dict[str, Any] | None,
) -> dict[str, Any]:
    slug = _slug(model)
    run_dir = out_root / f"model_{slug}"
    design = build_classic_cw_static_design(
        design_id=f"m2_phase2a_l2a_{slug}",
        postprocess_mode="none",
        diagnostic_ref=diagnostic_ref,
        positive_savings_only=True,
    )
    t0 = time.perf_counter()
    try:
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
            solver_id=f"m2_l2a_{slug}",
            display_name=f"M2 L2a · {model}",
            mode="live",
            endpoint=endpoint,
            model=model,
            api_key_env=api_key_env,
            max_requests=max_requests,
            request_timeout_s=120.0,
            wall_seconds=360.0,
            require_evolved=True,
        )
        return {
            "model": model,
            "slug": slug,
            "ok": True,
            "error": None,
            "wall_s": round(time.perf_counter() - t0, 2),
            "baseline_dev24": res["baseline_objective"],
            "best_dev24": res["best_objective"],
            "evaluations_total": res["evaluations_total"],
            "evaluations_valid": res["evaluations_valid"],
            "evolved_count": res["evolved_count"],
            "requests": res["resource_ledger"]["requests"],
            "frozen_solver": res["frozen_solver"],
            "frozen_manifest_path": res["frozen_manifest_path"],
        }
    except Exception as exc:
        return {
            "model": model,
            "slug": slug,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "wall_s": round(time.perf_counter() - t0, 2),
            "baseline_dev24": None,
            "best_dev24": None,
            "evaluations_total": 0,
            "evaluations_valid": 0,
            "evolved_count": 0,
            "requests": {},
            "frozen_solver": None,
            "frozen_manifest_path": None,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--out-root", type=Path, default=_REPO / "experiments" / "milestone2" / "phase2a_multimodel")
    parser.add_argument("--endpoint", default="https://opencode.ai/zen/go/v1/chat/completions")
    parser.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    parser.add_argument("--pop-size", type=int, default=3)
    parser.add_argument("--n-pop", type=int, default=2)
    parser.add_argument("--max-sample-nums", type=int, default=8)
    parser.add_argument("--max-requests", type=int, default=16)
    parser.add_argument("--search-seed", type=int, default=20261122)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args(argv)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    diag_json = _REPO / "experiments" / "milestone2" / "diagnostics" / "gap_decomposition_2x3.json"
    diag_ref = None
    if diag_json.is_file():
        import hashlib
        diag_ref = {
            "path": "experiments/milestone2/diagnostics/gap_decomposition_2x3.json",
            "sha256": hashlib.sha256(diag_json.read_bytes()).hexdigest(),
            "usage_role": "dev_selection",
        }

    results: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers, len(args.models))) as pool:
        futs = [
            pool.submit(
                _run_one_model,
                m,
                out_root=out_root,
                endpoint=args.endpoint,
                api_key_env=args.api_key_env,
                pop_size=args.pop_size,
                n_pop=args.n_pop,
                max_sample_nums=args.max_sample_nums,
                max_requests=args.max_requests,
                search_seed=args.search_seed,
                diagnostic_ref=diag_ref,
            )
            for m in args.models
        ]
        for fut in futs:
            results.append(fut.result())

    # Preserve input order
    by_model = {r["model"]: r for r in results}
    ordered = [by_model[m] for m in args.models]
    frozen_solvers = [
        FrozenInterfaceSolver.from_dict(r["frozen_solver"])
        for r in ordered
        if r["ok"] and r["frozen_solver"] is not None
    ]

    bundle_dir = out_root / "workbench_bundle_500ms"
    dash_dir = out_root / "dashboard_500ms"
    wb_res = None
    dash_res = None
    summary_means: dict[str, Any] = {}
    scale_drifts: dict[str, list[float]] = {}

    if frozen_solvers:
        wb_res = run_frozen_workbench_bundle(
            bundle_dir,
            frozen_solvers=frozen_solvers,
            reference_solver_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
            suite_specs=(
                ("cvrp_dev_hetero_24", "dev_train"),
                ("cvrp_select_multiscale_64", "selection"),
            ),
            budget_id="standard_500ms",
            time_budget_ms=500.0,
        )
        dash_res = build_dashboard(
            bundle_dir=bundle_dir,
            workspace_dir=_REPO / "knowledge_workspace",
            output_dir=dash_dir,
            release_id="m2-phase2a-multimodel-500ms",
        )
        wb_sum = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
        for sid, sdata in wb_sum["suites"].items():
            summary_means[sid] = {
                aid: {
                    "mean_tour_length": sdata["algorithms"][aid]["overall"]["mean_tour_length"],
                    "solve_ms_p50": sdata["algorithms"][aid]["overall"]["solve_ms_p50"],
                    "completion_rate": sdata["algorithms"][aid]["overall"]["completion_rate"],
                }
                for aid in sdata["algorithms"]
            }
        stress = json.loads((bundle_dir / "results" / "scale_stress_records.json").read_text(encoding="utf-8"))
        for row in stress.get("records", []):
            if row.get("scale_drift_pct") is not None:
                scale_drifts.setdefault(row["algorithm_id"], []).append(float(row["scale_drift_pct"]))

    comparison_rows: list[dict[str, Any]] = []
    for r in ordered:
        sid = f"m2_l2a_{r['slug']}"
        dev_m = summary_means.get("cvrp_dev_hetero_24", {}).get(sid, {})
        sel_m = summary_means.get("cvrp_select_multiscale_64", {}).get(sid, {})
        drifts = scale_drifts.get(sid, [])
        comparison_rows.append({
            "model": r["model"],
            "solver_id": sid,
            "ok": r["ok"],
            "error": r["error"],
            "wall_s": r["wall_s"],
            "evaluations_valid": r["evaluations_valid"],
            "evaluations_total": r["evaluations_total"],
            "evolved_count": r["evolved_count"],
            "completed_requests": r["requests"].get("completed_requests", 0),
            "prompt_tokens": r["requests"].get("prompt_tokens", 0),
            "completion_tokens": r["requests"].get("completion_tokens", 0),
            "total_tokens": r["requests"].get("total_tokens", 0),
            "dev_24_mean": dev_m.get("mean_tour_length"),
            "select_64_mean": sel_m.get("mean_tour_length"),
            "select_64_solve_ms_p50": sel_m.get("solve_ms_p50"),
            "max_scale_drift_pct": max(drifts) if drifts else None,
        })

    report = {
        "schema_version": "m2-phase2a-multimodel-comparison/v1",
        "config": {
            "endpoint": args.endpoint,
            "pop_size": args.pop_size,
            "n_pop": args.n_pop,
            "max_sample_nums": args.max_sample_nums,
            "max_requests": args.max_requests,
            "search_seed": args.search_seed,
            "operators": ["e1", "e2", "m1", "m2"],
        },
        "reference_baselines": {
            sid: {
                aid: summary_means.get(sid, {}).get(aid)
                for aid in ("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge")
            }
            for sid in ("cvrp_dev_hetero_24", "cvrp_select_multiscale_64")
        },
        "models": comparison_rows,
        "workbench_bundle": wb_res,
        "dashboard": dash_res,
    }
    report_path = out_root / "multimodel_comparison.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
