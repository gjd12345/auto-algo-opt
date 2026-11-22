"""Compute exact CVRP scale-drift fix, mechanism clustering, and Milestone 1.5 candidate shortlist."""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.pointwise_adapter import compile_pointwise_rule, execute_pointwise_rule
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID


def main() -> None:
    leg_p = REPO / "experiments" / "milestone15" / "legacy_reproduction_605.json"
    scr_p = REPO / "experiments" / "milestone15" / "workbench_screening_605.json"
    leg = json.loads(leg_p.read_text(encoding="utf-8"))
    scr = json.loads(scr_p.read_text(encoding="utf-8"))

    dev24 = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    nom_by_id = {inst["instance_id"]: inst for inst in dev24["instances"]}
    stress = dev24["scale_stress_instances"]

    scale_inv_cnt = 0
    scale_drifts = []
    for row in scr["cvrp_rows"]:
        p = REPO / "experiments" / row["path"].replace("\\", "/")
        code = p.read_text(encoding="utf-8")
        try:
            fn = compile_pointwise_rule(code, f"sc_{row['rank_by_objective']}")
            drifts = []
            for s_inst in stress:
                pid = s_inst["parent_instance_id"]
                r_nom = execute_pointwise_rule(fn, nom_by_id[pid], record_trace=False, time_budget_ms=500.0)
                r_sc = execute_pointwise_rule(fn, s_inst, record_trace=False, time_budget_ms=500.0)
                if r_nom["valid"] and r_sc["valid"]:
                    norm = float(r_sc["tour_length"]) / float(s_inst["coord_scale"])
                    drifts.append(abs(norm - float(r_nom["tour_length"])) / float(r_nom["tour_length"]) * 100.0)
            md = round(max(drifts), 4) if drifts else None
        except Exception:
            md = None
        row["max_scale_drift_pct"] = md
        if md is not None:
            scale_drifts.append((md, row["rank_by_objective"], row["mean_sel64"]))
            if md < 0.01:
                scale_inv_cnt += 1

    scr["cvrp_summary"]["scale_invariant_lt_0_01pct"] = scale_inv_cnt
    scr["cvrp_summary"]["top15_by_sel64"] = sorted(
        [r for r in scr["cvrp_rows"] if r["ok_92"] == 92 and r["mean_sel64"] is not None],
        key=lambda r: r["mean_sel64"],
    )[:15]
    scr_p.write_text(json.dumps(scr, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CVRP true scale_invariant (<0.01%): {scale_inv_cnt}/207")
    print("CVRP worst 5 scale drifts:", sorted(scale_drifts, reverse=True)[:5])

    ma = leg["midterm_sessions_audit"]
    print("Midterm dev4 NN runs (incl _aborted):", ma["dev4_nn_fingerprint_runs_including_aborted"])
    fp_map: dict[str, list[str]] = {}
    for s in ma["sessions"]:
        if s.get("route_fp_88"):
            fp_map.setdefault(s["route_fp_88"], []).append(s["run_name"])
    print("Midterm duplicate 88-inst route_fp:", {k: v for k, v in fp_map.items() if len(v) > 1})
    print(
        "Midterm top-6 by sel64:",
        [(s["run_name"], s["mean_sel64"], s["early_returns_88"], s["nn_identical_instances_of_88"])
         for s in sorted([s for s in ma["sessions"] if s.get("mean_sel64")], key=lambda x: x["mean_sel64"])[:6]],
    )

    print("\n--- CVRP Top 12 (92/92) by sel64 ---")
    for r in scr["cvrp_summary"]["top15_by_sel64"][:12]:
        print(
            f"  rank={r['rank_by_objective']:3d} sel64={r['mean_sel64']:.4f} arch={r['archived_objective']:.4f} "
            f"drift={r['max_scale_drift_pct']} early={r['runtime_voluntary_early_returns_88']} "
            f"winsR5={r['sel64_wins_vs_r5']} winsVBS={r['sel64_wins_vs_r5_r7_vbs']} p50={r['solve_ms_p50']:.2f}ms {r['path']}"
        )

    print("\n--- CVRP Scale-Invariant Top 8 (drift < 0.01%, 92/92) ---")
    si_rows = sorted(
        [r for r in scr["cvrp_rows"] if r["ok_92"] == 92 and r["max_scale_drift_pct"] is not None and r["max_scale_drift_pct"] < 0.01],
        key=lambda r: r["mean_sel64"],
    )
    for r in si_rows[:8]:
        print(
            f"  rank={r['rank_by_objective']:3d} sel64={r['mean_sel64']:.4f} arch={r['archived_objective']:.4f} "
            f"drift={r['max_scale_drift_pct']} early={r['runtime_voluntary_early_returns_88']} "
            f"winsR5={r['sel64_wins_vs_r5']} p50={r['solve_ms_p50']:.2f}ms {r['path']}"
        )

    print("\n--- TSP Top 12 (128/128) by gap ---")
    for r in scr["tsp_summary"]["top15_complete128_by_gap"][:12]:
        print(
            f"  rank={r['rank_by_objective']:3d} ok={r['ok_128']}/128 gap={r['mean_rel_gap_completed']:.5f} "
            f"arch={r['archived_objective']:.5f} p50={r['solve_ms_p50']:.2f}ms depth={r['ast']['ast_loop_depth']} "
            f"dest={r['ast']['ast_dest_pull']} ratio={r['ast']['ast_dimensionless_ratio']} {r['path']}"
        )

    print("\n--- OBP Top 12 (7/7) by gap ---")
    for r in scr["obp_summary"]["top15_complete7_by_gap"][:12]:
        print(
            f"  rank={r['rank_by_objective']:3d} ok={r['ok_7']}/7 gap={r['mean_rel_gap_completed']:.5f} "
            f"arch={r['archived_objective']:.5f} drift10x={r['cap_scale_10x_drift_pct']} "
            f"p50={r['solve_ms_p50']:.2f}ms consts={r['ast']['ast_hardcoded_cap_consts']} {r['path']}"
        )

    print("\n--- OBP Worst 6 10x Capacity Drift ---")
    for r in scr["obp_summary"]["worst_capacity_10x_drift"][:6]:
        print(
            f"  rank={r['rank_by_objective']:3d} arch={r['archived_objective']:.5f} "
            f"drift10x={r['cap_scale_10x_drift_pct']}% c100={r['bins_base_c100']} c1000={r['bins_scaled_c1000']} "
            f"consts={r['ast']['ast_hardcoded_cap_consts']} {r['path']}"
        )


if __name__ == "__main__":
    main()
