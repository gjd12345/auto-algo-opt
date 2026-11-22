"""Unified multi-problem (CVRP / TSP / OBP) Workbench evaluation runner and bundle exporter.

Produces a single authoritative set of per-instance records, routes/tours/packings,
step-by-step pointwise traces, summaries, Direction-2 selection artifacts, and
physically separated ``published_results/*.json`` consumed identically by CLI,
automated tests, and the offline research frontend.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite

from .protocol import extract_instance_features
from .selection import evaluate_frozen_transfer_portfolio, evaluate_oof_portfolio
from .solvers import (
    MILESTONE15_CVRP_IDS,
    POINTWISE_BASE_8_IDS,
    POINTWISE_PLUS_M15_IDS,
    POINTWISE_PLUS_S2_12_IDS,
    REFERENCE_7_IDS,
    SOLVER_CATALOG,
    UPSTREAM_CVRP_IDS,
    evaluate_algorithm_on_instance,
)
from .suites import BENCHMARK_ID, WORKBENCH_BENCHMARKS_DIR, load_shared_diagnostic_6
from .tsp_obp import (
    OBP_SOLVER_CATALOG,
    TSP_SOLVER_CATALOG,
    evaluate_obp_algorithm_on_instance,
    evaluate_tsp_algorithm_on_instance,
)

# All 13 registered multi-problem suites across 3 tiers
WORKBENCH_SUITES: tuple[tuple[str, str], ...] = (
    # Tier 1: Top-Venue Protocol
    ("cvrp_ext_eohs_256", "heldout"),
    ("cvrp_ext_reevo_scale", "heldout"),
    ("tsp_ext_eohs_128", "heldout"),
    ("obp_ext_eoh_weibull", "heldout"),
    # Tier 2: OR Gold Standard
    ("cvrp_ext_cvrplib_abp_74", "heldout"),
    ("cvrp_ext_cvrplib_x_100", "heldout"),
    ("tsp_ext_tsplib_euc2d", "heldout"),
    ("obp_ext_bpplib", "heldout"),
    # Tier 3: Local Controlled CVRP
    ("cvrp_dev_hetero_24", "dev_train"),
    ("cvrp_select_multiscale_64", "selection"),
    ("cvrp_hist_p0_120", "heldout"),
    ("cvrp_hist_hetero_288", "heldout"),
    ("cvrp_final_accept_120", "heldout"),
)


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_compact_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(np.asarray(values, dtype=float), q)), 4)


def aggregate_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute canonical summary statistics from a slice of per-instance records.

    Shared identically by CLI, automated tests, and the offline frontend.
    """
    n = len(records)
    if n == 0:
        return {
            "n_instances": 0,
            "ok_count": 0,
            "completion_rate": 0.0,
            "mean_tour_length": None,
            "total_tour_length": None,
            "mean_rel_gap": None,
            "median_rel_gap": None,
            "mean_route_count": None,
            "vehicle_limit_checked": 0,
            "vehicle_limit_compliance_rate": None,
            "exact_k_checked": 0,
            "exact_k_count": 0,
            "lt_k_count": 0,
            "gt_k_count": 0,
            "exact_k_compliance_rate": None,
            "exact_k_mean_rel_gap": None,
            "budget_exhausted_count": 0,
            "ok_budget_exhausted_count": 0,
            "timeout_count": 0,
            "local_opt_convergence_rate": None,
            "preprocess_ms_p50": None,
            "solve_ms_p50": None,
            "solve_ms_p95": None,
            "solve_ms_mean": None,
            "verify_ms_p50": None,
            "total_voluntary_early_returns": 0,
        }
    ok_rows = [r for r in records if r.get("status") == "ok" and r.get("tour_length") is not None]
    lengths = [float(r["tour_length"]) for r in ok_rows]
    gaps = [float(r["rel_gap"]) for r in ok_rows if r.get("rel_gap") is not None]
    routes_cnt = [int(r["route_count"]) for r in ok_rows if r.get("route_count") is not None]
    pre_ms = [float(r["preprocess_ms"]) for r in records if r.get("preprocess_ms") is not None]
    sol_ms = [float(r["solve_ms"]) for r in records if r.get("solve_ms") is not None]
    ver_ms = [float(r["verify_ms"]) for r in records if r.get("verify_ms") is not None]
    veh_checked = [r for r in ok_rows if r.get("within_vehicle_limit") is not None]
    veh_ok = sum(1 for r in veh_checked if r.get("within_vehicle_limit") is True)
    exact_checked = [r for r in ok_rows if r.get("target_vehicles") is not None and r.get("route_count") is not None]
    exact_k_rows = [r for r in exact_checked if int(r["route_count"]) == int(r["target_vehicles"])]
    lt_k_count = sum(1 for r in exact_checked if int(r["route_count"]) < int(r["target_vehicles"]))
    gt_k_count = sum(1 for r in exact_checked if int(r["route_count"]) > int(r["target_vehicles"]))
    exact_gaps = [float(r["rel_gap"]) for r in exact_k_rows if r.get("rel_gap") is not None]
    budget_ex = sum(1 for r in records if r.get("budget_exhausted") is True)
    ok_budget_ex = sum(1 for r in ok_rows if r.get("budget_exhausted") is True)
    timeout_cnt = sum(1 for r in records if r.get("status") == "timeout")
    early_ret = sum(int(r.get("voluntary_early_return_count") or 0) for r in ok_rows)

    return {
        "n_instances": n,
        "ok_count": len(ok_rows),
        "completion_rate": round(len(ok_rows) / n, 6),
        "mean_tour_length": round(float(np.mean(lengths)), 4) if lengths else None,
        "total_tour_length": round(float(np.sum(lengths)), 4) if lengths else None,
        "mean_rel_gap": round(float(np.mean(gaps)), 6) if gaps else None,
        "median_rel_gap": round(float(np.median(gaps)), 6) if gaps else None,
        "mean_route_count": round(float(np.mean(routes_cnt)), 3) if routes_cnt else None,
        "vehicle_limit_checked": len(veh_checked),
        "vehicle_limit_compliance_rate": round(veh_ok / len(veh_checked), 6) if veh_checked else None,
        "exact_k_checked": len(exact_checked),
        "exact_k_count": len(exact_k_rows),
        "lt_k_count": lt_k_count,
        "gt_k_count": gt_k_count,
        "exact_k_compliance_rate": round(len(exact_k_rows) / len(exact_checked), 6) if exact_checked else None,
        "exact_k_mean_rel_gap": round(float(np.mean(exact_gaps)), 6) if exact_gaps else None,
        "budget_exhausted_count": budget_ex,
        "ok_budget_exhausted_count": ok_budget_ex,
        "timeout_count": timeout_cnt,
        "local_opt_convergence_rate": round((len(ok_rows) - ok_budget_ex) / n, 6),
        "preprocess_ms_p50": _quantile(pre_ms, 50),
        "solve_ms_p50": _quantile(sol_ms, 50),
        "solve_ms_p95": _quantile(sol_ms, 95),
        "solve_ms_mean": round(float(np.mean(sol_ms)), 4) if sol_ms else None,
        "verify_ms_p50": _quantile(ver_ms, 50),
        "total_voluntary_early_returns": early_ret,
    }


TRACE_POINTWISE_CORE_IDS: frozenset[str] = frozenset({
    "nn",
    "savings_pointwise",
    "s2_r4_cos",
    "s2_r5_spiral",
    "s2_r7_iso",
    "c",
    "s2_ctrl_best",
    "eohs_cvrp_f1",
    "i605_cvrp_c1_tworegime",
})


def _should_store_trace(suite_id: str, inst_index: int, inst: Mapping[str, Any], alg_id: str) -> bool:
    if suite_id == "shared_diagnostic_6":
        return True
    if alg_id not in TRACE_POINTWISE_CORE_IDS:
        return False
    if suite_id == "cvrp_dev_hetero_24":
        return True
    if suite_id == "cvrp_select_multiscale_64":
        return (inst_index % 6) == 0
    if suite_id == "cvrp_ext_cvrplib_abp_74":
        return (inst_index % 6) == 0
    if suite_id == "cvrp_ext_cvrplib_x_100":
        return int(inst.get("size", 0)) <= 220 and (inst_index % 4) == 0
    if suite_id == "cvrp_ext_eohs_256":
        return (inst_index % 24) == 0
    if suite_id == "cvrp_ext_reevo_scale":
        return (inst_index % 8) == 0
    if suite_id in {"cvrp_hist_p0_120", "cvrp_final_accept_120"}:
        return (inst_index % 40) < 3
    if suite_id == "cvrp_hist_hetero_288":
        return (inst_index % 16) == 0
    return inst_index < 6


def run_workbench_evaluation(
    bundle_dir: Path,
    *,
    budget_id: str = "standard_500ms",
    time_budget_ms: float = 500.0,
) -> dict[str, Any]:
    """Run full multi-problem Milestone-1 evaluation across all 13+1 suites and export bundle."""
    bundle_dir = Path(bundle_dir).resolve()
    suites_dir = bundle_dir / "suites"
    results_dir = bundle_dir / "results"
    routes_dir = bundle_dir / "routes"
    traces_dir = bundle_dir / "traces"
    pub_dest = bundle_dir / "published_results"
    for d in (suites_dir, results_dir, routes_dir, traces_dir, pub_dest):
        d.mkdir(parents=True, exist_ok=True)

    # Copy frozen published_results/*.json verbatim into the release bundle
    pub_src = WORKBENCH_BENCHMARKS_DIR / "published_results"
    if pub_src.is_dir():
        for src_file in sorted(pub_src.glob("*.json")):
            shutil.copy2(src_file, pub_dest / src_file.name)

    # CVRP extra algorithms per suite (Milestone 1 + frozen Milestone 1.5 representatives)
    suite_extra_algs: dict[str, tuple[str, ...]] = {
        "cvrp_ext_eohs_256": (*UPSTREAM_CVRP_IDS, *MILESTONE15_CVRP_IDS),
        "cvrp_ext_reevo_scale": (*UPSTREAM_CVRP_IDS, *MILESTONE15_CVRP_IDS),
        "cvrp_ext_cvrplib_abp_74": (*UPSTREAM_CVRP_IDS, *MILESTONE15_CVRP_IDS),
        "cvrp_ext_cvrplib_x_100": (*UPSTREAM_CVRP_IDS, *MILESTONE15_CVRP_IDS),
        "cvrp_hist_hetero_288": (
            *tuple(a for a in POINTWISE_PLUS_S2_12_IDS if a not in REFERENCE_7_IDS),
            *MILESTONE15_CVRP_IDS,
        ),
        "cvrp_select_multiscale_64": ("a", "b", "c", "v0", "dd_load", "radial", "s2_r3_rho", "s2_ctrl_best", *MILESTONE15_CVRP_IDS),
        "cvrp_final_accept_120": ("a", "b", "c", "v0", "dd_load", "radial", "s2_r3_rho", "s2_ctrl_best", "eohs_cvrp_f1", "heuragenix_min_cost_ins", *MILESTONE15_CVRP_IDS),
        "cvrp_hist_p0_120": ("a", "b", "c", "v0", "s2_r3_rho", "s2_ctrl_best", *MILESTONE15_CVRP_IDS),
        "shared_diagnostic_6": ("a", "b", "c", "v0", "s2_r3_rho", "s2_ctrl_best", "eohs_cvrp_f1", "heuragenix_min_cost_ins", *MILESTONE15_CVRP_IDS),
        "cvrp_dev_hetero_24": ("c", "v0", "s2_ctrl_best", "eohs_cvrp_f1", "heuragenix_min_cost_ins", *MILESTONE15_CVRP_IDS),
    }

    loaded_suites: list[dict[str, Any]] = []
    for profile, split in WORKBENCH_SUITES:
        suite = load_profile_suite(BENCHMARK_ID, profile, split=split)
        loaded_suites.append({
            "suite_id": profile,
            "benchmark_id": BENCHMARK_ID,
            "problem_family": suite.get("problem_family") or "cvrp",
            "benchmark_tier": suite.get("benchmark_tier") or "local_controlled",
            "split": suite["split"],
            "suite_role": suite["suite_role"],
            "exposure_status": suite["exposure_status"],
            "distance_convention": suite["distance_convention"],
            "vehicle_limit_policy": suite["vehicle_limit_policy"],
            "reference_kind": suite["instances"][0].get("reference_kind"),
            "data_manifest_hash": suite["data_manifest_hash"],
            "reference_manifest_hash": suite["reference_manifest_hash"],
            "benchmark_spec_hash": suite["benchmark_spec_hash"],
            "selection_manifest_hash": suite.get("selection_manifest_hash"),
            "published_results_path": suite.get("published_results_path"),
            "published_results_hash": suite.get("published_results_hash"),
            "metadata": suite.get("metadata", {}),
            "instances": suite["instances"],
            "scale_stress_instances": suite.get("scale_stress_instances", []),
        })

    # Append read-only shared_diagnostic_6
    sh6_instances = load_shared_diagnostic_6()
    loaded_suites.append({
        "suite_id": "shared_diagnostic_6",
        "benchmark_id": "historical_evidence",
        "problem_family": "cvrp",
        "benchmark_tier": "local_controlled",
        "split": "dev_train",
        "suite_role": "historical_regression",
        "exposure_status": "historically_exposed",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "reference_kind": "solver_reference",
        "data_manifest_hash": hashlib.sha256(
            json.dumps(sh6_instances, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "reference_manifest_hash": None,
        "benchmark_spec_hash": None,
        "selection_manifest_hash": None,
        "published_results_path": None,
        "published_results_hash": None,
        "metadata": {
            "source_file": "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json",
            "description": "Shared 6-instance diagnostic suite (Frozen C = 10.9197, R5 = 10.2714 with 17 voluntary early returns).",
        },
        "instances": sh6_instances,
        "scale_stress_instances": [],
    })

    # Warm-up CVRP, TSP, OBP solvers once to remove import/JIT jitter
    warm_cvrp = next(s["instances"][0] for s in loaded_suites if s["problem_family"] == "cvrp")
    for alg_id in SOLVER_CATALOG:
        evaluate_algorithm_on_instance(alg_id, warm_cvrp, record_trace=False, time_budget_ms=time_budget_ms)
    extract_instance_features(warm_cvrp)
    warm_tsp = next(s["instances"][0] for s in loaded_suites if s["problem_family"] == "tsp")
    for alg_id in TSP_SOLVER_CATALOG:
        evaluate_tsp_algorithm_on_instance(alg_id, warm_tsp, time_budget_ms=time_budget_ms)
    warm_obp = next(s["instances"][0] for s in loaded_suites if s["problem_family"] == "obp")
    for alg_id in OBP_SOLVER_CATALOG:
        evaluate_obp_algorithm_on_instance(alg_id, warm_obp, time_budget_ms=time_budget_ms)

    all_records: list[dict[str, Any]] = []
    scale_stress_records: list[dict[str, Any]] = []
    suite_catalog_index: list[dict[str, Any]] = []
    summary_by_suite: dict[str, Any] = {}
    selection_inputs: dict[str, list[dict[str, Any]]] = {}

    for suite in loaded_suites:
        suite_id = suite["suite_id"]
        family = suite["problem_family"]
        dist_conv = suite["distance_convention"]
        veh_pol = suite["vehicle_limit_policy"]
        instances = suite["instances"]

        if family == "cvrp":
            algs_for_suite = list(REFERENCE_7_IDS) + list(suite_extra_algs.get(suite_id, ()))
        elif family == "tsp":
            algs_for_suite = list(TSP_SOLVER_CATALOG.keys())
        elif family == "obp":
            algs_for_suite = list(OBP_SOLVER_CATALOG.keys())
        else:
            raise ValueError(f"unsupported_family:{family}")

        # Prepare enriched suite payload (compact for large OBP streams so browser loads fast)
        suite_features_rows: dict[str, dict[str, Any]] = {}
        enriched_instances: list[dict[str, Any]] = []
        for inst in instances:
            iid = str(inst["instance_id"])
            if family == "cvrp":
                feats, feat_ms = extract_instance_features(inst)
                suite_features_rows[iid] = {
                    "instance_id": iid,
                    "cell": inst.get("cell"),
                    "size": int(inst["size"]),
                    "spatial": inst.get("spatial"),
                    "depot_style": inst.get("depot_style"),
                    "capacity_level": inst.get("capacity_level"),
                    "demand_dist": inst.get("demand_dist"),
                    "features": {k: round(v, 6) for k, v in feats.items()},
                    "feat_ms": round(feat_ms, 4),
                    "costs": {},
                    "solve_ms": {},
                }
                enriched_instances.append({**inst, "features": {k: round(v, 6) for k, v in feats.items()}})
            elif family == "obp":
                items_arr = np.asarray(inst["items"], dtype=np.float64)
                cap = float(inst["capacity"])
                ratios = items_arr / cap
                hist10, _ = np.histogram(ratios, bins=np.linspace(0.0, 1.000001, 11))
                # Store compact summary stats + first 400 sample items in suite JSON for fast UI rendering
                slim = {k: v for k, v in inst.items() if k != "items"}
                slim["item_stats"] = {
                    "count": int(items_arr.size),
                    "sum": round(float(items_arr.sum()), 2),
                    "mean": round(float(items_arr.mean()), 4),
                    "std": round(float(items_arr.std()), 4),
                    "min": round(float(items_arr.min()), 2),
                    "max": round(float(items_arr.max()), 2),
                    "mean_cap_ratio": round(float(ratios.mean()), 4),
                    "ratio_histogram_10": [int(c) for c in hist10],
                }
                enriched_instances.append(slim)
            else:
                enriched_instances.append(dict(inst))

        suite_payload = {
            "suite_id": suite_id,
            "benchmark_id": suite["benchmark_id"],
            "problem_family": family,
            "benchmark_tier": suite["benchmark_tier"],
            "split": suite["split"],
            "suite_role": suite["suite_role"],
            "exposure_status": suite["exposure_status"],
            "distance_convention": dist_conv,
            "vehicle_limit_policy": veh_pol,
            "reference_kind": suite["reference_kind"],
            "data_manifest_hash": suite["data_manifest_hash"],
            "reference_manifest_hash": suite["reference_manifest_hash"],
            "benchmark_spec_hash": suite["benchmark_spec_hash"],
            "selection_manifest_hash": suite.get("selection_manifest_hash"),
            "published_results_path": suite.get("published_results_path"),
            "published_results_hash": suite.get("published_results_hash"),
            "instance_count": len(enriched_instances),
            "algorithms_evaluated": algs_for_suite,
            "metadata": suite["metadata"],
            "instances": enriched_instances,
        }
        suite_file = suites_dir / f"{suite_id}.json"
        suite_sha = _write_compact_json(suite_file, suite_payload)

        suite_catalog_index.append({
            "suite_id": suite_id,
            "path": f"suites/{suite_id}.json",
            "sha256": suite_sha,
            "benchmark_id": suite["benchmark_id"],
            "problem_family": family,
            "benchmark_tier": suite["benchmark_tier"],
            "split": suite["split"],
            "suite_role": suite["suite_role"],
            "exposure_status": suite["exposure_status"],
            "distance_convention": dist_conv,
            "vehicle_limit_policy": veh_pol,
            "reference_kind": suite["reference_kind"],
            "instance_count": len(enriched_instances),
            "algorithms_evaluated": algs_for_suite,
            "data_manifest_hash": suite["data_manifest_hash"],
            "selection_manifest_hash": suite.get("selection_manifest_hash"),
            "published_results_path": suite.get("published_results_path"),
            "metadata": suite["metadata"],
        })

        suite_routes_map: dict[str, dict[str, Any]] = {}
        suite_traces_map: dict[str, dict[str, Any]] = {}
        suite_records: list[dict[str, Any]] = []

        for idx, inst in enumerate(instances):
            iid = str(inst["instance_id"])
            suite_routes_map[iid] = {}

            if family == "cvrp":
                # Keep official BKS routes inside routes map too for seamless Page 3 overlay
                if isinstance(inst.get("bks_routes"), list):
                    suite_routes_map[iid]["__bks__"] = {
                        "routes": inst["bks_routes"],
                        "tour_length": inst.get("bks_recomputed_nint_cost") or inst.get("reference_objective"),
                        "rel_gap": 0.0,
                        "is_bks_overlay": True,
                    }
                for alg_id in algs_for_suite:
                    spec = SOLVER_CATALOG[alg_id]
                    want_trace = spec.kind == "pointwise" and _should_store_trace(suite_id, idx, inst, alg_id)
                    res = evaluate_algorithm_on_instance(
                        alg_id,
                        inst,
                        distance_convention=dist_conv,
                        vehicle_limit_policy=veh_pol,
                        time_budget_ms=time_budget_ms,
                        record_trace=want_trace,
                    )
                    record = {
                        "suite_id": suite_id,
                        "problem_family": "cvrp",
                        "benchmark_tier": suite["benchmark_tier"],
                        "suite_role": suite["suite_role"],
                        "exposure_status": suite["exposure_status"],
                        "comparison_mode": "local_recomputed",
                        "budget_id": budget_id,
                        "budget_ms": time_budget_ms,
                        "instance_id": iid,
                        "cell": inst.get("cell"),
                        "size": int(inst["size"]),
                        "spatial": inst.get("spatial"),
                        "depot_style": inst.get("depot_style"),
                        "capacity_level": inst.get("capacity_level"),
                        "demand_dist": inst.get("demand_dist"),
                        "cvrplib_set": inst.get("cvrplib_set"),
                        "x_tier": inst.get("x_tier"),
                        "algorithm_id": alg_id,
                        "paradigm": spec.paradigm,
                        "interface": spec.interface,
                        "kb_entry_id": spec.kb_entry_id,
                        "status": res["status"],
                        "valid": res["valid"],
                        "error_code": res["error_code"],
                        "tour_length": round(float(res["tour_length"]), 6) if res["tour_length"] is not None else None,
                        "reference_objective": round(float(res["reference_objective"]), 6) if res["reference_objective"] is not None else None,
                        "reference_kind": res["reference_kind"],
                        "rel_gap": res["rel_gap"],
                        "route_count": res["route_count"],
                        "max_utilization": res["max_utilization"],
                        "mean_utilization": res["mean_utilization"],
                        "target_vehicles": res["target_vehicles"],
                        "within_vehicle_limit": res["within_vehicle_limit"],
                        "exact_vehicle_count": res["exact_vehicle_count"],
                        "vehicle_count_delta": res["vehicle_count_delta"],
                        "preprocess_ms": res["preprocess_ms"],
                        "solve_ms": res["solve_ms"],
                        "verify_ms": res["verify_ms"],
                        "voluntary_early_return_count": res["voluntary_early_return_count"],
                        "forced_capacity_return_count": res["forced_capacity_return_count"],
                        "budget_exhausted": res["budget_exhausted"],
                        "has_trace": bool(res["trace_steps"]),
                    }
                    suite_records.append(record)
                    all_records.append(record)
                    suite_routes_map[iid][alg_id] = {
                        "routes": res["routes"],
                        "route_loads": res["route_loads"],
                        "route_distances": res["route_distances"],
                        "tour_length": record["tour_length"],
                        "rel_gap": record["rel_gap"],
                        "voluntary_early_return_count": record["voluntary_early_return_count"],
                    }
                    if res["trace_steps"]:
                        suite_traces_map.setdefault(iid, {})[alg_id] = res["trace_steps"]
                    if res["valid"] and res["tour_length"] is not None:
                        suite_features_rows[iid]["costs"][alg_id] = float(res["tour_length"])
                        suite_features_rows[iid]["solve_ms"][alg_id] = float(res["solve_ms"])

            elif family == "tsp":
                if isinstance(inst.get("opt_tour"), list):
                    suite_routes_map[iid]["__opt__"] = {
                        "tour": inst["opt_tour"],
                        "tour_length": inst.get("reference_objective"),
                        "rel_gap": 0.0,
                        "is_bks_overlay": True,
                    }
                for alg_id in algs_for_suite:
                    spec = TSP_SOLVER_CATALOG[alg_id]
                    res = evaluate_tsp_algorithm_on_instance(
                        alg_id,
                        inst,
                        distance_convention=dist_conv,
                        time_budget_ms=time_budget_ms,
                    )
                    record = {
                        "suite_id": suite_id,
                        "problem_family": "tsp",
                        "benchmark_tier": suite["benchmark_tier"],
                        "suite_role": suite["suite_role"],
                        "exposure_status": suite["exposure_status"],
                        "comparison_mode": "local_recomputed",
                        "budget_id": budget_id,
                        "budget_ms": time_budget_ms,
                        "instance_id": iid,
                        "cell": inst.get("cell"),
                        "size": int(inst["size"]),
                        "spatial": inst.get("spatial"),
                        "algorithm_id": alg_id,
                        "paradigm": spec.paradigm,
                        "interface": spec.interface,
                        "kb_entry_id": spec.kb_entry_id,
                        "status": res["status"],
                        "valid": res["valid"],
                        "error_code": res["error_code"],
                        "tour_length": round(float(res["tour_length"]), 6) if res["tour_length"] is not None else None,
                        "reference_objective": round(float(res["reference_objective"]), 6) if res["reference_objective"] is not None else None,
                        "reference_kind": res["reference_kind"],
                        "rel_gap": res["rel_gap"],
                        "route_count": 1 if res["valid"] else 0,
                        "preprocess_ms": res["preprocess_ms"],
                        "solve_ms": res["solve_ms"],
                        "verify_ms": res["verify_ms"],
                        "voluntary_early_return_count": 0,
                        "budget_exhausted": res["budget_exhausted"],
                        "has_trace": False,
                    }
                    suite_records.append(record)
                    all_records.append(record)
                    suite_routes_map[iid][alg_id] = {
                        "tour": res["tour"],
                        "tour_length": record["tour_length"],
                        "rel_gap": record["rel_gap"],
                    }

            elif family == "obp":
                for alg_id in algs_for_suite:
                    spec = OBP_SOLVER_CATALOG[alg_id]
                    res = evaluate_obp_algorithm_on_instance(
                        alg_id,
                        inst,
                        time_budget_ms=time_budget_ms,
                    )
                    record = {
                        "suite_id": suite_id,
                        "problem_family": "obp",
                        "benchmark_tier": suite["benchmark_tier"],
                        "suite_role": suite["suite_role"],
                        "exposure_status": suite["exposure_status"],
                        "comparison_mode": "local_recomputed",
                        "budget_id": budget_id,
                        "budget_ms": time_budget_ms,
                        "instance_id": iid,
                        "cell": inst.get("cell"),
                        "obp_regime": inst.get("obp_regime"),
                        "bpplib_subset": inst.get("bpplib_subset"),
                        "size": int(inst["size"]),
                        "capacity": int(inst["capacity"]),
                        "algorithm_id": alg_id,
                        "paradigm": spec.paradigm,
                        "interface": spec.interface,
                        "kb_entry_id": spec.kb_entry_id,
                        "status": res["status"],
                        "valid": res["valid"],
                        "error_code": res["error_code"],
                        "tour_length": res["tour_length"],
                        "bins_used": res["bins_used"],
                        "reference_objective": res["reference_objective"],
                        "reference_kind": res["reference_kind"],
                        "rel_gap": res["rel_gap"],
                        "route_count": res["bins_used"],
                        "mean_fill_rate": res["mean_fill_rate"],
                        "full_bins_count": res["full_bins_count"],
                        "preprocess_ms": res["preprocess_ms"],
                        "solve_ms": res["solve_ms"],
                        "verify_ms": res["verify_ms"],
                        "voluntary_early_return_count": 0,
                        "budget_exhausted": res["budget_exhausted"],
                        "has_trace": False,
                    }
                    suite_records.append(record)
                    all_records.append(record)
                    suite_routes_map[iid][alg_id] = {
                        "bins_used": res["bins_used"],
                        "tour_length": res["tour_length"],
                        "rel_gap": res["rel_gap"],
                        "mean_fill_rate": res["mean_fill_rate"],
                        "min_fill_rate": res["min_fill_rate"],
                        "full_bins_count": res["full_bins_count"],
                        "total_slack": res["total_slack"],
                        "fill_histogram_10": res["fill_histogram_10"],
                        "sample_bin_fills": res["sample_bin_fills"],
                    }

        _write_compact_json(routes_dir / f"{suite_id}.json", {
            "suite_id": suite_id,
            "problem_family": family,
            "budget_id": budget_id,
            "routes_by_instance": suite_routes_map,
        })
        if suite_traces_map:
            _write_compact_json(traces_dir / f"{suite_id}.json", {
                "suite_id": suite_id,
                "budget_id": budget_id,
                "traces_by_instance": suite_traces_map,
            })

        # Scale-stress checks (cvrp_dev_hetero_24 1e-3 coordinate scaling)
        if family == "cvrp" and suite["scale_stress_instances"]:
            for s_inst in suite["scale_stress_instances"]:
                parent_id = s_inst["parent_instance_id"]
                scale_val = float(s_inst["coord_scale"])
                for alg_id in algs_for_suite:
                    res_s = evaluate_algorithm_on_instance(
                        alg_id,
                        s_inst,
                        distance_convention=dist_conv,
                        vehicle_limit_policy=veh_pol,
                        time_budget_ms=time_budget_ms,
                        record_trace=False,
                    )
                    parent_rec = next(
                        r for r in suite_records
                        if r["instance_id"] == parent_id and r["algorithm_id"] == alg_id
                    )
                    norm_len = (float(res_s["tour_length"]) / scale_val) if res_s["tour_length"] is not None else None
                    drift_pct = (
                        round(100.0 * abs(norm_len - float(parent_rec["tour_length"])) / max(float(parent_rec["tour_length"]), 1e-12), 4)
                        if (norm_len is not None and parent_rec["tour_length"] is not None)
                        else None
                    )
                    scale_stress_records.append({
                        "suite_id": suite_id,
                        "instance_id": s_inst["instance_id"],
                        "parent_instance_id": parent_id,
                        "coord_scale": scale_val,
                        "algorithm_id": alg_id,
                        "status": res_s["status"],
                        "nominal_tour_length": parent_rec["tour_length"],
                        "scaled_normalized_tour_length": round(norm_len, 6) if norm_len is not None else None,
                        "scale_drift_pct": drift_pct,
                    })

        # Build per-suite summaries (overall + common_completed + by_scale + by_spatial / by_cvrplib_set / by_x_tier / by_obp_regime)
        ok_ids_by_alg: dict[str, set[str]] = {
            alg_id: {
                str(r["instance_id"])
                for r in suite_records
                if r["algorithm_id"] == alg_id and r.get("status") == "ok" and r.get("tour_length") is not None
            }
            for alg_id in algs_for_suite
        }
        all_inst_ids = {str(inst["instance_id"]) for inst in instances}
        strict_all_common_ids = set(all_inst_ids)
        for s_ids in ok_ids_by_alg.values():
            strict_all_common_ids &= s_ids

        # Primary apples-to-apples intersection excluding slow diagnostic rules
        # (O(n^3) s2_r7_iso in CVRP and O(n^4) i605_tsp_t1_rollout in TSP) so they do not collapse
        # common_completed for fast solvers while strict_all_common_completed preserves full intersection.
        primary_algs = [
            a for a in algs_for_suite if a not in {"s2_r7_iso", "i605_tsp_t1_rollout"}
        ] or list(algs_for_suite)
        primary_common_ids = set(all_inst_ids)
        for a in primary_algs:
            primary_common_ids &= ok_ids_by_alg[a]

        alg_summaries: dict[str, Any] = {}
        for alg_id in algs_for_suite:
            rows_a = [r for r in suite_records if r["algorithm_id"] == alg_id]
            by_scale = {
                str(sz): aggregate_records([r for r in rows_a if int(r["size"]) == sz])
                for sz in sorted({int(r["size"]) for r in rows_a})
            }
            by_spatial = {
                sp: aggregate_records([r for r in rows_a if r.get("spatial") == sp])
                for sp in sorted({str(r["spatial"]) for r in rows_a if r.get("spatial")})
            }
            extra_breakdowns: dict[str, Any] = {}
            if suite_id == "cvrp_ext_cvrplib_abp_74":
                extra_breakdowns["by_cvrplib_set"] = {
                    cset: aggregate_records([r for r in rows_a if r.get("cvrplib_set") == cset])
                    for cset in ("A", "B", "P")
                }
            if suite_id == "cvrp_ext_cvrplib_x_100":
                extra_breakdowns["by_x_tier"] = {
                    tier: aggregate_records([r for r in rows_a if r.get("x_tier") == tier])
                    for tier in ("X-S (100-250)", "X-M (251-500)", "X-L (501-1000)")
                }
            if family == "obp":
                regimes = sorted({str(r["obp_regime"]) for r in rows_a if r.get("obp_regime")})
                if regimes:
                    extra_breakdowns["by_obp_regime"] = {
                        reg: aggregate_records([r for r in rows_a if r.get("obp_regime") == reg])
                        for reg in regimes
                    }
            alg_summaries[alg_id] = {
                "overall": aggregate_records(rows_a),
                "common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in primary_common_ids]),
                "strict_all_common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in strict_all_common_ids]),
                "by_scale": by_scale,
                "by_spatial": by_spatial,
                **extra_breakdowns,
            }

        summary_by_suite[suite_id] = {
            "suite_id": suite_id,
            "problem_family": family,
            "benchmark_tier": suite["benchmark_tier"],
            "suite_role": suite["suite_role"],
            "exposure_status": suite["exposure_status"],
            "distance_convention": dist_conv,
            "vehicle_limit_policy": veh_pol,
            "reference_kind": suite["reference_kind"],
            "comparison_mode": "local_recomputed",
            "budget_id": budget_id,
            "budget_ms": time_budget_ms,
            "n_instances": len(instances),
            "common_completed_count": len(primary_common_ids),
            "common_completed_algorithms": primary_algs,
            "strict_all_common_completed_count": len(strict_all_common_ids),
            "algorithms": alg_summaries,
        }

        if suite_id in {"cvrp_hist_hetero_288", "cvrp_select_multiscale_64", "cvrp_final_accept_120"}:
            selection_inputs[suite_id] = [suite_features_rows[str(inst["instance_id"])] for inst in instances]

    # Direction-2 portfolio & selection evaluations
    selection_analyses: dict[str, Any] = {}
    if "cvrp_hist_hetero_288" in selection_inputs:
        rows_288 = selection_inputs["cvrp_hist_hetero_288"]
        selection_analyses["hetero_288__pointwise_base"] = evaluate_oof_portfolio(
            "cvrp_hist_hetero_288", "pointwise_base", rows_288, POINTWISE_BASE_8_IDS, protocols=("cv12", "loro48", "loso3")
        )
        selection_analyses["hetero_288__pointwise_plus_s2"] = evaluate_oof_portfolio(
            "cvrp_hist_hetero_288", "pointwise_plus_s2", rows_288, POINTWISE_PLUS_S2_12_IDS, protocols=("cv12", "loro48", "loso3")
        )
        selection_analyses["hetero_288__pointwise_plus_m15"] = evaluate_oof_portfolio(
            "cvrp_hist_hetero_288", "pointwise_plus_m15", rows_288, POINTWISE_PLUS_M15_IDS, protocols=("cv12", "loro48", "loso3")
        )
        selection_analyses["hetero_288__multiparadigm_7"] = evaluate_oof_portfolio(
            "cvrp_hist_hetero_288", "multiparadigm_7", rows_288, REFERENCE_7_IDS, protocols=("cv12", "loro48", "loso3")
        )

    if "cvrp_select_multiscale_64" in selection_inputs and "cvrp_final_accept_120" in selection_inputs:
        tr_64 = selection_inputs["cvrp_select_multiscale_64"]
        te_120 = selection_inputs["cvrp_final_accept_120"]
        selection_analyses["final_accept_120__pointwise_plus_s2_frozen"] = evaluate_frozen_transfer_portfolio(
            train_suite_id="cvrp_select_multiscale_64",
            test_suite_id="cvrp_final_accept_120",
            portfolio_id="pointwise_plus_s2_frozen",
            train_rows=tr_64,
            test_rows=te_120,
            members=POINTWISE_PLUS_S2_12_IDS,
        )
        selection_analyses["final_accept_120__pointwise_plus_m15_frozen"] = evaluate_frozen_transfer_portfolio(
            train_suite_id="cvrp_select_multiscale_64",
            test_suite_id="cvrp_final_accept_120",
            portfolio_id="pointwise_plus_m15_frozen",
            train_rows=tr_64,
            test_rows=te_120,
            members=POINTWISE_PLUS_M15_IDS,
        )
        selection_analyses["final_accept_120__multiparadigm_7_frozen"] = evaluate_frozen_transfer_portfolio(
            train_suite_id="cvrp_select_multiscale_64",
            test_suite_id="cvrp_final_accept_120",
            portfolio_id="multiparadigm_7_frozen",
            train_rows=tr_64,
            test_rows=te_120,
            members=REFERENCE_7_IDS,
        )

    # Export unified multi-problem algorithms catalog (CVRP + TSP + OBP)
    alg_rows: list[dict[str, Any]] = []
    for spec in SOLVER_CATALOG.values():
        alg_rows.append({
            "algorithm_id": spec.algorithm_id,
            "problem_family": "cvrp",
            "display_name": spec.display_name,
            "paradigm": spec.paradigm,
            "interface": spec.interface,
            "kind": spec.kind,
            "kb_entry_id": spec.kb_entry_id,
            "code_path": spec.code_path,
            "code_sha256": spec.code_sha256,
            "code_source": spec.code_source,
            "upstream_commit": spec.upstream_commit,
            "comparison_mode": spec.comparison_mode,
            "is_core_reference": spec.is_core_reference,
            "default_budget_ms": spec.default_budget_ms,
            "description": spec.description,
        })
    for catalog in (TSP_SOLVER_CATALOG, OBP_SOLVER_CATALOG):
        for spec in catalog.values():
            alg_rows.append({
                "algorithm_id": spec.algorithm_id,
                "problem_family": spec.problem_family,
                "display_name": spec.display_name,
                "paradigm": spec.paradigm,
                "interface": spec.interface,
                "kind": spec.problem_family,
                "kb_entry_id": spec.kb_entry_id,
                "code_path": spec.code_path,
                "code_sha256": spec.code_sha256,
                "code_source": spec.code_source,
                "upstream_commit": spec.upstream_commit,
                "comparison_mode": spec.comparison_mode,
                "is_core_reference": True,
                "default_budget_ms": 500.0,
                "description": spec.description,
            })

    _write_json(bundle_dir / "algorithms.json", {
        "schema_version": "cvrp-workbench-algorithms/v2",
        "core_reference_ids": list(REFERENCE_7_IDS),
        "upstream_cvrp_ids": list(UPSTREAM_CVRP_IDS),
        "pointwise_base_8_ids": list(POINTWISE_BASE_8_IDS),
        "pointwise_plus_s2_12_ids": list(POINTWISE_PLUS_S2_12_IDS),
        "tsp_solver_ids": list(TSP_SOLVER_CATALOG.keys()),
        "obp_solver_ids": list(OBP_SOLVER_CATALOG.keys()),
        "algorithms": alg_rows,
    })

    _write_json(suites_dir / "index.json", {
        "schema_version": "cvrp-workbench-suites-index/v2",
        "generated_at": _utc_now(),
        "suites": suite_catalog_index,
    })

    _write_compact_json(results_dir / "per_instance_records.json", {
        "schema_version": "cvrp-workbench-per-instance-records/v2",
        "generated_at": _utc_now(),
        "comparison_mode": "local_recomputed",
        "budget_id": budget_id,
        "budget_ms": time_budget_ms,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
        "record_count": len(all_records),
        "records": all_records,
    })

    _write_json(results_dir / "summary.json", {
        "schema_version": "cvrp-workbench-summary/v2",
        "generated_at": _utc_now(),
        "comparison_mode": "local_recomputed",
        "budget_id": budget_id,
        "budget_ms": time_budget_ms,
        "core_reference_ids": list(REFERENCE_7_IDS),
        "suites": summary_by_suite,
    })

    _write_json(results_dir / "scale_stress_records.json", {
        "schema_version": "cvrp-workbench-scale-stress/v1",
        "generated_at": _utc_now(),
        "record_count": len(scale_stress_records),
        "records": scale_stress_records,
    })

    _write_compact_json(results_dir / "selection_records.json", {
        "schema_version": "cvrp-workbench-selection-records/v1",
        "generated_at": _utc_now(),
        "budget_id": budget_id,
        "analyses": selection_analyses,
    })

    bundle_files = []
    for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file() and p.name != "workbench_manifest.json"):
        bundle_files.append({
            "path": path.relative_to(bundle_dir).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        })
    wb_manifest = {
        "schema_version": "cvrp-workbench-bundle/v2",
        "generated_at": _utc_now(),
        "budget_id": budget_id,
        "budget_ms": time_budget_ms,
        "suite_count": len(suite_catalog_index),
        "record_count": len(all_records),
        "selection_analysis_count": len(selection_analyses),
        "files": bundle_files,
    }
    _write_json(bundle_dir / "workbench_manifest.json", wb_manifest)

    return {
        "ok": True,
        "bundle_dir": str(bundle_dir),
        "suite_count": len(suite_catalog_index),
        "record_count": len(all_records),
        "scale_stress_count": len(scale_stress_records),
        "selection_analyses": list(selection_analyses.keys()),
        "file_count": len(bundle_files) + 1,
    }
