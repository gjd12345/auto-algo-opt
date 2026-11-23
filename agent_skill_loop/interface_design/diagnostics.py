"""Formalized exploratory 2-constructor-family x 3-postprocessing gap decomposition diagnostic (Task 2A-2).

Exports complete, reproducible per-instance evidence (raw & postprocessed cost, verification
status, outcome class, timing breakdown, run parameters, and local-search stop reason) for
4 baseline solvers (``nn``, ``s2_r5_spiral``, ``i605_cvrp_c1_tworegime``, ``cw_parallel_merge``)
across ``cvrp_dev_hetero_24`` and ``cvrp_select_multiscale_64``.

Explicitly records ``usage_role = "dev_selection"`` and refuses any ``locked_m2_blind`` suite.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import prepare_instance_arrays, verify_cvrp_solution
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID

from .blind_commitment import assert_suite_not_blind
from .contracts import classify_outcome
from .templates import apply_intra_2opt, apply_relocate_2opt

DEFAULT_DIAGNOSTIC_CONSTRUCTORS: tuple[tuple[str, str], ...] = (
    ("nn", "sequential_construct"),
    ("s2_r5_spiral", "sequential_construct"),
    ("i605_cvrp_c1_tworegime", "sequential_construct"),
    ("cw_parallel_merge", "parallel_merge"),
)

DEFAULT_DIAGNOSTIC_SUITES: tuple[tuple[str, str], ...] = (
    ("cvrp_dev_hetero_24", "dev_train"),
    ("cvrp_select_multiscale_64", "selection"),
)


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_gap_decomposition_diagnostic(
    *,
    output_dir: Path,
    suites: Sequence[tuple[str, str]] = DEFAULT_DIAGNOSTIC_SUITES,
    constructors: Sequence[tuple[str, str]] = DEFAULT_DIAGNOSTIC_CONSTRUCTORS,
    time_budget_ms: float | None = 500.0,
    max_two_opt_passes: int = 200,
    max_relocate_outer_passes: int = 80,
    usage_role: str = "dev_selection",
) -> dict[str, Any]:
    """Run 2-family x 3-postprocess exploratory diagnostic and write JSON/CSV/Markdown artifacts."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    run_params = {
        "usage_role": usage_role,
        "diagnostic_kind": "exploratory_2family_x_3postprocess",
        "time_budget_ms": time_budget_ms,
        "max_two_opt_passes": max_two_opt_passes,
        "max_relocate_outer_passes": max_relocate_outer_passes,
        "constructors": [{"algorithm_id": cid, "family": fam} for cid, fam in constructors],
        "suites": [{"suite_id": sid, "split": sp} for sid, sp in suites],
    }

    records: list[dict[str, Any]] = []
    summary_by_suite: dict[str, Any] = {}

    for suite_id, split in suites:
        assert_suite_not_blind(suite_id)
        suite = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
        assert_suite_not_blind(suite_id, suite)
        dist_conv = suite["distance_convention"]
        veh_pol = suite["vehicle_limit_policy"]
        instances = suite["instances"]

        suite_rows: list[dict[str, Any]] = []

        for inst in instances:
            iid = str(inst["instance_id"])
            t_pre0 = time.perf_counter()
            matrix, demands, capacity = prepare_instance_arrays(inst, distance_convention=dist_conv)
            pre_ms = (time.perf_counter() - t_pre0) * 1000.0

            for alg_id, family in constructors:
                # 1. Raw construction via authoritative M1 workbench solver
                raw_res = evaluate_algorithm_on_instance(
                    alg_id,
                    inst,
                    distance_convention=dist_conv,
                    vehicle_limit_policy=veh_pol,
                    time_budget_ms=time_budget_ms,
                    record_trace=False,
                )
                raw_valid = bool(raw_res["valid"])
                raw_len = float(raw_res["tour_length"]) if raw_res["tour_length"] is not None else None
                raw_routes = raw_res["routes"]
                raw_solve_ms = float(raw_res["solve_ms"])
                raw_budget_ex = bool(raw_res["budget_exhausted"])

                raw_row = {
                    "suite_id": suite_id,
                    "usage_role": usage_role,
                    "instance_id": iid,
                    "size": int(inst["size"]),
                    "spatial": inst.get("spatial"),
                    "constructor_id": alg_id,
                    "constructor_family": family,
                    "postprocess_mode": "raw",
                    "raw_tour_length": round(raw_len, 6) if raw_len is not None else None,
                    "final_tour_length": round(raw_len, 6) if raw_len is not None else None,
                    "improvement_abs": 0.0 if raw_len is not None else None,
                    "improvement_pct": 0.0 if raw_len is not None else None,
                    "route_count": int(raw_res["route_count"]),
                    "status": raw_res["status"],
                    "valid": raw_valid,
                    "error_code": raw_res["error_code"],
                    "outcome_class": classify_outcome(
                        valid=raw_valid, status=str(raw_res["status"]), budget_exhausted=raw_budget_ex
                    ),
                    "stop_reason": "time_budget_exhausted" if raw_budget_ex else "completed",
                    "two_opt_moves": 0,
                    "relocate_moves": 0,
                    "outer_passes": 0,
                    "preprocess_ms": round(float(raw_res["preprocess_ms"]), 4),
                    "construct_ms": round(raw_solve_ms, 4),
                    "postprocess_ms": 0.0,
                    "total_solve_ms": round(raw_solve_ms, 4),
                    "verify_ms": round(float(raw_res["verify_ms"]), 4),
                    "budget_exhausted": raw_budget_ex,
                    "time_budget_ms": time_budget_ms,
                }
                records.append(raw_row)
                suite_rows.append(raw_row)

                # 2. Same intra-route 2-opt & 3. Same Relocate+2-opt
                for mode in ("intra_2opt", "relocate_2opt"):
                    if not raw_valid or raw_len is None:
                        fail_row = {
                            **raw_row,
                            "postprocess_mode": mode,
                            "final_tour_length": None,
                            "improvement_abs": None,
                            "improvement_pct": None,
                            "stop_reason": "raw_construction_failed",
                        }
                        records.append(fail_row)
                        suite_rows.append(fail_row)
                        continue

                    rem_ms = (time_budget_ms - raw_solve_ms) if time_budget_ms is not None else None
                    if raw_budget_ex or (rem_ms is not None and rem_ms <= 0.0):
                        post_routes = raw_routes
                        post_meta = {
                            "two_opt_moves": 0,
                            "relocate_moves": 0,
                            "outer_passes": 0,
                            "stop_reason": "skipped_budget_exhausted",
                            "budget_exhausted": True,
                            "postprocess_ms": 0.0,
                        }
                    else:
                        deadline = (time.perf_counter() + rem_ms / 1000.0) if rem_ms is not None else None
                        if mode == "intra_2opt":
                            post_routes, post_meta = apply_intra_2opt(
                                raw_routes,
                                matrix,
                                deadline=deadline,
                                max_passes=max_two_opt_passes,
                            )
                        else:
                            post_routes, post_meta = apply_relocate_2opt(
                                raw_routes,
                                matrix,
                                demands,
                                capacity,
                                deadline=deadline,
                                max_outer_passes=max_relocate_outer_passes,
                            )

                    ver = verify_cvrp_solution(
                        inst,
                        post_routes,
                        distance_convention=dist_conv,
                        vehicle_limit_policy=veh_pol,
                        expected_matrix=matrix,
                        submitted_matrix=matrix,
                        expected_demands=demands,
                        submitted_demands=demands,
                    )
                    fin_len = float(ver["tour_length"]) if (ver["valid"] and ver["tour_length"] is not None) else None
                    imp_abs = (raw_len - fin_len) if fin_len is not None else None
                    imp_pct = (100.0 * imp_abs / max(raw_len, 1e-12)) if imp_abs is not None else None
                    bud_ex = bool(raw_budget_ex or post_meta["budget_exhausted"])
                    st = "ok" if ver["valid"] else "infeasible"
                    p_ms = float(post_meta["postprocess_ms"])

                    row = {
                        "suite_id": suite_id,
                        "usage_role": usage_role,
                        "instance_id": iid,
                        "size": int(inst["size"]),
                        "spatial": inst.get("spatial"),
                        "constructor_id": alg_id,
                        "constructor_family": family,
                        "postprocess_mode": mode,
                        "raw_tour_length": round(raw_len, 6),
                        "final_tour_length": round(fin_len, 6) if fin_len is not None else None,
                        "improvement_abs": round(imp_abs, 6) if imp_abs is not None else None,
                        "improvement_pct": round(imp_pct, 4) if imp_pct is not None else None,
                        "route_count": int(ver["route_count"]),
                        "status": st,
                        "valid": bool(ver["valid"]),
                        "error_code": ver["error_code"],
                        "outcome_class": classify_outcome(valid=bool(ver["valid"]), status=st, budget_exhausted=bud_ex),
                        "stop_reason": str(post_meta["stop_reason"]),
                        "two_opt_moves": int(post_meta["two_opt_moves"]),
                        "relocate_moves": int(post_meta["relocate_moves"]),
                        "outer_passes": int(post_meta["outer_passes"]),
                        "preprocess_ms": round(pre_ms, 4),
                        "construct_ms": round(raw_solve_ms, 4),
                        "postprocess_ms": round(p_ms, 4),
                        "total_solve_ms": round(raw_solve_ms + p_ms, 4),
                        "verify_ms": round(float(ver["verify_ms"]), 4),
                        "budget_exhausted": bud_ex,
                        "time_budget_ms": time_budget_ms,
                    }
                    records.append(row)
                    suite_rows.append(row)

        # Aggregate matrix for this suite
        matrix_summary: dict[str, dict[str, Any]] = {}
        for alg_id, family in constructors:
            per_mode: dict[str, Any] = {}
            for mode in ("raw", "intra_2opt", "relocate_2opt"):
                cell_rows = [r for r in suite_rows if r["constructor_id"] == alg_id and r["postprocess_mode"] == mode]
                ok_lens = [float(r["final_tour_length"]) for r in cell_rows if r["valid"] and r["final_tour_length"] is not None]
                stop_counts: dict[str, int] = {}
                outcome_counts: dict[str, int] = {}
                for r in cell_rows:
                    sr = str(r["stop_reason"])
                    stop_counts[sr] = stop_counts.get(sr, 0) + 1
                    oc = str(r["outcome_class"])
                    outcome_counts[oc] = outcome_counts.get(oc, 0) + 1
                per_mode[mode] = {
                    "n_instances": len(cell_rows),
                    "ok_count": len(ok_lens),
                    "mean_tour_length": round(float(np.mean(ok_lens)), 4) if ok_lens else None,
                    "mean_total_solve_ms": round(float(np.mean([float(r["total_solve_ms"]) for r in cell_rows])), 4) if cell_rows else None,
                    "stop_reason_counts": stop_counts,
                    "outcome_counts": outcome_counts,
                }
            matrix_summary[alg_id] = {"constructor_family": family, "modes": per_mode}

        # Bridging decomposition relative to bare cw_parallel_merge
        cw_raw_mean = matrix_summary.get("cw_parallel_merge", {}).get("modes", {}).get("raw", {}).get("mean_tour_length")
        cw_reloc_mean = matrix_summary.get("cw_parallel_merge", {}).get("modes", {}).get("relocate_2opt", {}).get("mean_tour_length")
        bridging: dict[str, Any] = {}
        if cw_raw_mean is not None:
            for alg_id, _ in constructors:
                a_raw = matrix_summary[alg_id]["modes"]["raw"]["mean_tour_length"]
                a_rel = matrix_summary[alg_id]["modes"]["relocate_2opt"]["mean_tour_length"]
                if a_raw is not None and a_rel is not None:
                    entry: dict[str, Any] = {
                        "raw_mean": a_raw,
                        "relocate_2opt_mean": a_rel,
                        "postprocess_drop_pct": round(100.0 * (a_raw - a_rel) / max(a_raw, 1e-12), 2),
                    }
                    if alg_id != "cw_parallel_merge" and a_raw > cw_raw_mean:
                        entry["bridged_gap_to_cw_raw_pct"] = round(100.0 * (a_raw - a_rel) / (a_raw - cw_raw_mean), 2)
                        entry["remaining_gap_vs_cw_raw_pct"] = round(100.0 * (a_rel - cw_raw_mean) / cw_raw_mean, 2)
                    bridging[alg_id] = entry
            if cw_reloc_mean is not None:
                bridging["cw_marginal_postprocess_drop_pct"] = round(100.0 * (cw_raw_mean - cw_reloc_mean) / cw_raw_mean, 2)

        summary_by_suite[suite_id] = {
            "suite_id": suite_id,
            "n_instances": len(instances),
            "data_manifest_hash": suite["data_manifest_hash"],
            "matrix": matrix_summary,
            "bridging_vs_cw_raw": bridging,
        }

    payload = {
        "schema_version": "m2-gap-decomposition-diagnostic/v1",
        "generated_at": _utc_now(),
        "run_params": run_params,
        "record_count": len(records),
        "summary_by_suite": summary_by_suite,
        "records": records,
    }
    json_path = output_dir / "gap_decomposition_2x3.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    json_sha = hashlib.sha256(json_path.read_bytes()).hexdigest()

    csv_path = output_dir / "gap_decomposition_2x3_records.csv"
    if records:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

    # Human-readable Markdown summary
    md_lines = [
        "# Milestone 2 Exploratory Diagnostic: 2 Constructor Families x 3 Postprocessing Modes",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Usage role: `{usage_role}` (strictly isolated from `cvrp_m2_blind_120`)",
        f"- Time budget per instance: `{time_budget_ms} ms`",
        f"- JSON SHA-256: `{json_sha}`",
        "",
    ]
    for suite_id, sdata in summary_by_suite.items():
        md_lines.append(f"## `{suite_id}` (n={sdata['n_instances']})")
        md_lines.append("")
        md_lines.append("| Constructor ID | Family | Raw | +2-opt | +Relocate+2-opt | Post Drop % | Bridged vs CW Raw % | Remaining vs CW Raw % |")
        md_lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for alg_id, _ in constructors:
            m = sdata["matrix"][alg_id]["modes"]
            b = sdata["bridging_vs_cw_raw"].get(alg_id, {})
            br = f"{b['bridged_gap_to_cw_raw_pct']:.2f}%" if "bridged_gap_to_cw_raw_pct" in b else "—"
            rem = f"{b['remaining_gap_vs_cw_raw_pct']:+.2f}%" if "remaining_gap_vs_cw_raw_pct" in b else "0.00%"
            md_lines.append(
                f"| `{alg_id}` | `{sdata['matrix'][alg_id]['constructor_family']}` | "
                f"{m['raw']['mean_tour_length']:.4f} | {m['intra_2opt']['mean_tour_length']:.4f} | "
                f"{m['relocate_2opt']['mean_tour_length']:.4f} | {b.get('postprocess_drop_pct', 0.0):.2f}% | {br} | {rem} |"
            )
        md_lines.append("")
    md_path = output_dir / "gap_decomposition_2x3.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")

    return {
        "ok": True,
        "json_path": str(json_path),
        "json_sha256": json_sha,
        "csv_path": str(csv_path),
        "md_path": str(md_path),
        "record_count": len(records),
        "summary_by_suite": summary_by_suite,
    }


def analyze_instance_records(
    records: Sequence[Mapping[str, Any]],
    *,
    instance_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    baseline_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Template-agnostic 5-factor slicing, headroom & win/tie/loss summary over instance records."""
    base_by_id: dict[str, Mapping[str, Any]] = {
        str(r.get("instance_id")): r for r in (baseline_records or ()) if r.get("instance_id")
    }
    valid_objs = [
        float(r["tour_length"])
        for r in records
        if r.get("valid") and r.get("tour_length") is not None
    ]
    solve_times = sorted(float(r["solve_ms"]) for r in records if r.get("solve_ms") is not None)
    outcomes = {"completed": 0, "budget_exhausted_feasible_incumbent": 0, "timeout_or_infeasible": 0}
    for r in records:
        oc = str(r.get("outcome_class") or "timeout_or_infeasible")
        outcomes[oc] = outcomes.get(oc, 0) + 1

    slices: dict[str, dict[str, Any]] = {}
    for factor in ("size", "spatial", "depot_style", "capacity_level", "demand_dist"):
        buckets: dict[str, list[Mapping[str, Any]]] = {}
        for r in records:
            iid = str(r.get("instance_id") or "")
            meta = dict((instance_metadata or {}).get(iid) or r)
            val = meta.get(factor)
            if val is not None:
                buckets.setdefault(str(val), []).append(r)
        factor_summary: dict[str, Any] = {}
        for key, group in sorted(buckets.items()):
            objs = [float(x["tour_length"]) for x in group if x.get("valid") and x.get("tour_length") is not None]
            paired_deltas: list[float] = []
            wtl = {"wins": 0, "ties": 0, "losses": 0}
            for x in group:
                iid = str(x.get("instance_id") or "")
                b = base_by_id.get(iid)
                if b and x.get("valid") and b.get("valid") and x.get("tour_length") is not None and b.get("tour_length") is not None:
                    xv, bv = float(x["tour_length"]), float(b["tour_length"])
                    paired_deltas.append(100.0 * (xv - bv) / max(bv, 1e-12))
                    if xv < bv - 1e-9:
                        wtl["wins"] += 1
                    elif xv > bv + 1e-9:
                        wtl["losses"] += 1
                    else:
                        wtl["ties"] += 1
            factor_summary[key] = {
                "count": len(group),
                "valid_count": len(objs),
                "mean_tour_length": round(sum(objs) / len(objs), 4) if objs else None,
                "mean_delta_vs_baseline_pct": round(sum(paired_deltas) / len(paired_deltas), 4) if paired_deltas else None,
                "wtl_vs_baseline": wtl if paired_deltas else None,
                "exhausted_count": sum(1 for x in group if x.get("outcome_class") == "budget_exhausted_feasible_incumbent"),
            }
        slices[factor] = factor_summary

    def _pct(vals: list[float], p: float) -> float | None:
        if not vals:
            return None
        pos = min(len(vals) - 1, max(0, int(round((p / 100.0) * (len(vals) - 1)))))
        return round(vals[pos], 4)

    return {
        "instance_count": len(records),
        "valid_count": len(valid_objs),
        "mean_tour_length": round(sum(valid_objs) / len(valid_objs), 4) if valid_objs else None,
        "solve_ms_p50": _pct(solve_times, 50.0),
        "solve_ms_p95": _pct(solve_times, 95.0),
        "outcome_counts": outcomes,
        "slices": slices,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/milestone2/diagnostics"),
    )
    parser.add_argument("--time-budget-ms", type=float, default=500.0)
    args = parser.parse_args(argv)
    res = run_gap_decomposition_diagnostic(
        output_dir=args.output_dir,
        time_budget_ms=args.time_budget_ms,
    )
    print(json.dumps({k: v for k, v in res.items() if k != "summary_by_suite"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
