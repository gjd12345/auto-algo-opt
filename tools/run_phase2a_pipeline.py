"""Run the complete Milestone 2 Phase 2A narrow vertical slice end-to-end.

Steps:
  2A-1: Seal & verify cvrp_m2_blind_120 (public commitment in manifests/, sealed payload in .secrets/)
  2A-2: Run 2-constructor-family x 3-postprocess exploratory diagnostic on dev_24 & select_64
  2A-3: Validate cvrp_parallel_merge_static/v1 through all 5 gates & assert 0.0-error exact
        un-truncated CW equivalence (merge_sequence, routes, recomputed objective) + 500 ms check
  2A-4: Run DynamicInterfaceProblem + upstream EoH evolution (live LLM or deterministic mock)
        and export frozen_solver_manifest.json + resource_ledger.json
  2A-5: Run run_frozen_workbench_bundle (M2 frozen solver + R5 + C1 + CW) on standard 500 ms
        budget and build offline dashboard.html via existing frontend/build_dashboard.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.cvrp_workbench.runner import run_frozen_workbench_bundle
from agent_skill_loop.cvrp_workbench.solvers import solve_cw_parallel_merge
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_commitment import (
    BLIND_COMMITMENT_PATH,
    DEFAULT_SEALED_BLIND_PATH,
    seal_m2_blind_120,
    verify_sealed_against_commitment,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.diagnostics import run_gap_decomposition_diagnostic
from agent_skill_loop.interface_design.dynamic_eoh import run_dynamic_eoh_evolution
from agent_skill_loop.interface_design.runtime import compile_hook_function, evaluate_hook_on_instance_inprocess
from agent_skill_loop.interface_design.templates import (
    CLASSIC_CW_STATIC_HOOK_CODE,
    build_classic_cw_static_design,
    get_template_spec,
)
from agent_skill_loop.interface_design.validator import InterfaceValidator
from frontend.build_dashboard import build_dashboard

_REPO = Path(__file__).resolve().parents[1]


def _reference_cw_with_merges(
    distance_matrix: np.ndarray,
    demands: np.ndarray,
    capacity: float,
) -> tuple[list[list[int]], list[list[int]]]:
    """Reference un-truncated CW merge returning both normalized routes and exact merge sequence."""
    routes_ref, _ = solve_cw_parallel_merge(distance_matrix, demands, capacity, time_budget_ms=None)
    # Reproduce exact merge sequence from solvers.solve_cw_parallel_merge logic for 1:1 check
    n = int(distance_matrix.shape[0] - 1)
    iu, ju = np.triu_indices(n, k=1)
    i_idx = iu + 1
    j_idx = ju + 1
    sav = distance_matrix[0, i_idx] + distance_matrix[0, j_idx] - distance_matrix[i_idx, j_idx]
    pos = sav > 1e-12
    i_idx = i_idx[pos]
    j_idx = j_idx[pos]
    sav = sav[pos]
    order = np.argsort(-sav, kind="mergesort")
    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    route_load: dict[int, float] = {i: float(demands[i]) for i in range(1, n + 1)}
    owner = list(range(n + 1))
    merges: list[list[int]] = []
    for k in order:
        i = int(i_idx[k])
        j = int(j_idx[k])
        ri, rj = owner[i], owner[j]
        if ri == rj or route_load[ri] + route_load[rj] > capacity + 1e-12:
            continue
        seq_i, seq_j = routes[ri], routes[rj]
        i_start, i_end = seq_i[0] == i, seq_i[-1] == i
        j_start, j_end = seq_j[0] == j, seq_j[-1] == j
        if not ((i_start or i_end) and (j_start or j_end)):
            continue
        if i_start and not i_end:
            seq_i = seq_i[::-1]
        if j_end and not j_start:
            seq_j = seq_j[::-1]
        routes[ri] = seq_i + seq_j
        route_load[ri] += route_load[rj]
        for node in seq_j:
            owner[node] = ri
        del routes[rj]
        del route_load[rj]
        merges.append([i, j])
    return routes_ref, merges


def verify_cw_equivalence(out_path: Path) -> dict[str, Any]:
    """Assert 0.0-error un-truncated merge-sequence/route/objective equivalence + 500 ms budget check."""
    tpl = get_template_spec("cvrp_parallel_merge_static", "v1")
    hook_fn = compile_hook_function(
        CLASSIC_CW_STATIC_HOOK_CODE,
        hook_name=tpl.hook_name,
        expected_args=tpl.hook_signature,
    )
    checked = 0
    exact_merge_matches = 0
    exact_route_matches = 0
    max_obj_abs_diff = 0.0
    budget_500_outcomes: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    for suite_id, split in (("cvrp_dev_hetero_24", "dev_train"), ("cvrp_select_multiscale_64", "selection")):
        suite = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
        dist_conv = suite["distance_convention"]
        veh_pol = suite["vehicle_limit_policy"]
        for inst in suite["instances"]:
            matrix, demands, capacity = prepare_instance_arrays(inst, distance_convention=dist_conv)
            ref_routes, ref_merges = _reference_cw_with_merges(matrix, demands, capacity)
            ref_ver = verify_cvrp_solution(inst, ref_routes, distance_convention=dist_conv, vehicle_limit_policy=veh_pol)

            # Un-truncated exact equivalence run
            tpl_res = evaluate_hook_on_instance_inprocess(
                template_id="cvrp_parallel_merge_static",
                template_version="v1",
                hook_fn=hook_fn,
                instance=inst,
                postprocess_mode="none",
                template_options={"positive_savings_only": True},
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                time_budget_ms=None,
                capture_merge_sequence=True,
            )
            # Unified 500 ms check
            bud_res = evaluate_hook_on_instance_inprocess(
                template_id="cvrp_parallel_merge_static",
                template_version="v1",
                hook_fn=hook_fn,
                instance=inst,
                postprocess_mode="none",
                template_options={"positive_savings_only": True},
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                time_budget_ms=500.0,
                capture_merge_sequence=False,
            )

            merge_eq = tpl_res.get("merge_sequence") == ref_merges
            route_eq = tpl_res.get("routes") == ref_routes
            diff = abs(float(tpl_res["tour_length"]) - float(ref_ver["tour_length"]))
            max_obj_abs_diff = max(max_obj_abs_diff, diff)
            checked += 1
            if merge_eq:
                exact_merge_matches += 1
            if route_eq:
                exact_route_matches += 1
            oc = str(bud_res["outcome_class"])
            budget_500_outcomes[oc] = budget_500_outcomes.get(oc, 0) + 1
            rows.append({
                "suite_id": suite_id,
                "instance_id": inst["instance_id"],
                "merge_sequence_exact": merge_eq,
                "routes_exact": route_eq,
                "obj_abs_diff": diff,
                "ref_tour_length": round(float(ref_ver["tour_length"]), 6),
                "tpl_tour_length": round(float(tpl_res["tour_length"]), 6),
                "budget_500_outcome": oc,
                "budget_500_solve_ms": bud_res["solve_ms"],
                "budget_500_candidate_gen_ms": bud_res["candidate_gen_ms"],
                "budget_500_hook_ms": bud_res["hook_ms"],
                "budget_500_merge_ms": bud_res["merge_ms"],
            })

    summary = {
        "schema_version": "m2-phase2a-cw-equivalence/v1",
        "template_id": "cvrp_parallel_merge_static",
        "template_version": "v1",
        "template_source_sha256": tpl.template_source_sha256,
        "checked_instances": checked,
        "exact_merge_sequence_matches": exact_merge_matches,
        "exact_route_matches": exact_route_matches,
        "max_obj_abs_diff": max_obj_abs_diff,
        "all_exact": (exact_merge_matches == checked and exact_route_matches == checked and max_obj_abs_diff == 0.0),
        "budget_500_outcomes": budget_500_outcomes,
        "records": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not summary["all_exact"]:
        raise RuntimeError(
            f"cw_equivalence_failed:merges={exact_merge_matches}/{checked},routes={exact_route_matches}/{checked},diff={max_obj_abs_diff}"
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=_REPO / "experiments" / "milestone2")
    parser.add_argument("--eoh-mode", choices=("live", "mock"), default="live")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--endpoint", default="https://api.deepseek.com/v1/chat/completions")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--pop-size", type=int, default=2)
    parser.add_argument("--n-pop", type=int, default=1)
    parser.add_argument("--max-sample-nums", type=int, default=4)
    parser.add_argument("--search-seed", type=int, default=20261122)
    args = parser.parse_args(argv)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # 2A-1: Seal & verify blind commitment
    if not (BLIND_COMMITMENT_PATH.is_file() and DEFAULT_SEALED_BLIND_PATH.is_file()):
        seal_res = seal_m2_blind_120(
            commitment_path=BLIND_COMMITMENT_PATH,
            sealed_path=DEFAULT_SEALED_BLIND_PATH,
            overwrite=False,
        )
    else:
        seal_res = {"reused_existing": True}
    verify_blind_res = verify_sealed_against_commitment(
        sealed_path=DEFAULT_SEALED_BLIND_PATH,
        commitment_path=BLIND_COMMITMENT_PATH,
    )

    # 2A-2: Formal 2x3 exploratory diagnostic
    diag_dir = out_root / "diagnostics"
    diag_res = run_gap_decomposition_diagnostic(output_dir=diag_dir, time_budget_ms=500.0)

    # 2A-3: Exact CW equivalence + 5-gate validation of cvrp_parallel_merge_static/v1
    eq_path = out_root / "phase2a_cw_equivalence.json"
    eq_res = verify_cw_equivalence(eq_path)

    design = build_classic_cw_static_design(
        design_id="m2_phase2a_l2a_cw_static_raw",
        postprocess_mode="none",
        diagnostic_ref={
            "path": str(Path(diag_res["json_path"]).relative_to(_REPO).as_posix()),
            "sha256": diag_res["json_sha256"],
            "usage_role": "dev_selection",
        },
        positive_savings_only=True,
    )
    validator = InterfaceValidator(candidate_timeout_s=20.0, instance_time_budget_ms=500.0)
    val_report = validator.validate(design)
    (out_root / "phase2a_design_validation.json").write_text(
        json.dumps(val_report.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not val_report.passed:
        raise RuntimeError(f"phase2a_design_validation_failed:{[f.error_code for f in val_report.failures]}")

    # 2A-4: DynamicInterfaceProblem + real upstream EoH evolution -> FrozenInterfaceSolver
    eoh_dir = out_root / f"phase2a_eoh_{args.eoh_mode}"
    eoh_res = run_dynamic_eoh_evolution(
        design=design,
        output_dir=eoh_dir,
        suite_id="cvrp_dev_hetero_24",
        split="dev_train",
        pop_size=args.pop_size,
        n_pop=args.n_pop,
        max_sample_nums=args.max_sample_nums,
        search_seed=args.search_seed,
        solver_id=f"m2_eoh_l2a_merge_{args.eoh_mode}",
        display_name=f"M2 EoH Static Merge ({args.eoh_mode})",
        mode=args.eoh_mode,
        endpoint=args.endpoint,
        model=args.model,
        api_key_env=args.api_key_env,
        max_requests=args.max_requests,
    )
    frozen_solver = FrozenInterfaceSolver.from_dict(eoh_res["frozen_solver"])

    # 2A-5: Explicit Workbench frozen bundle + existing offline dashboard.html
    bundle_dir = out_root / f"phase2a_workbench_bundle_{args.eoh_mode}"
    wb_res = run_frozen_workbench_bundle(
        bundle_dir,
        frozen_solvers=[frozen_solver],
        reference_solver_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
        suite_specs=(
            ("cvrp_dev_hetero_24", "dev_train"),
            ("cvrp_select_multiscale_64", "selection"),
        ),
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )
    dash_dir = out_root / f"phase2a_dashboard_{args.eoh_mode}"
    dash_res = build_dashboard(
        bundle_dir=bundle_dir,
        workspace_dir=_REPO / "knowledge_workspace",
        output_dir=dash_dir,
        release_id=f"m2-phase2a-{args.eoh_mode}-500ms",
    )

    wb_summary = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    compact_means = {
        sid: {
            aid: sdata["algorithms"][aid]["overall"]["mean_tour_length"]
            for aid in sdata["algorithms"]
        }
        for sid, sdata in wb_summary["suites"].items()
    }

    report = {
        "ok": True,
        "step_2a1_blind_commitment": {
            "seal": seal_res,
            "verify": verify_blind_res,
            "commitment_path": str(BLIND_COMMITMENT_PATH),
        },
        "step_2a2_diagnostics": {
            "json_path": diag_res["json_path"],
            "json_sha256": diag_res["json_sha256"],
            "record_count": diag_res["record_count"],
        },
        "step_2a3_cw_equivalence_and_5gates": {
            "checked_instances": eq_res["checked_instances"],
            "exact_merge_sequence_matches": eq_res["exact_merge_sequence_matches"],
            "exact_route_matches": eq_res["exact_route_matches"],
            "max_obj_abs_diff": eq_res["max_obj_abs_diff"],
            "budget_500_outcomes": eq_res["budget_500_outcomes"],
            "validation_passed": val_report.passed,
            "template_source_sha256": val_report.template_source_sha256,
        },
        "step_2a4_dynamic_eoh": {
            "mode": eoh_res["mode"],
            "eoh_status": eoh_res["eoh_status"],
            "baseline_objective": eoh_res["baseline_objective"],
            "best_objective": eoh_res["best_objective"],
            "evaluations_total": eoh_res["evaluations_total"],
            "evaluations_valid": eoh_res["evaluations_valid"],
            "evolved_count": eoh_res["evolved_count"],
            "frozen_manifest_path": eoh_res["frozen_manifest_path"],
            "resource_ledger": eoh_res["resource_ledger"],
        },
        "step_2a5_workbench_and_dashboard": {
            "bundle_dir": wb_res["bundle_dir"],
            "record_count": wb_res["record_count"],
            "algorithms": wb_res["algorithms"],
            "mean_tour_lengths": compact_means,
            "dashboard_html": dash_res["dashboard_html"],
            "dashboard_sha256": dash_res["dashboard_sha256"],
        },
    }
    summary_path = out_root / f"phase2a_summary_{args.eoh_mode}.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
