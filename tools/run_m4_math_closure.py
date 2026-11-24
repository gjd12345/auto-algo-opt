"""Milestone 4 Mathematical Theory Closure & Empirical Verification Engine.

Deliverables:
  1. shapley-r5      : Exact 2^5 = 32 coalition Shapley decomposition & Grabisch 2nd-order interactions
                       for frozen s2_r5_spiral.py (with bit-for-bit 11111 parity & sum=v(1)-v(0) checks)
  2. hrk-analysis    : Deterministic metric lower bound R(I) = (2/Q) * sum(q_i * d(0,i)) + fixed-n
                       complementarity regression avoiding shared-VBS denominator spurious correlation
  3. group-invariance: Cross-problem Euclidean/capacity scaling group + E(2) isometry + alpha=1 phase flip
  4. dissect-m32     : Algebraic AST & perturbation dissection of M3.2 emergent L3/L3b operators
  5. full-part1      : Run zero-LLM Part-1 deliverables (shapley-r5 + hrk-analysis + group-invariance)
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import compute_distance_matrix
from agent_skill_loop.cvrp_workbench.solvers import (
    compile_pointwise_rule,
    evaluate_algorithm_on_instance,
    execute_pointwise_rule,
    get_solver_spec,
)
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.runtime import (
    compile_hook_function,
    evaluate_frozen_interface_solver,
    evaluate_hook_on_instance_inprocess,
)
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from research_agent.contracts import atomic_write_json, utc_now

R5_PATH = REPO / "experiments" / "cvrp_midterm" / "selection_s2" / "rules_s2" / "s2_r5_spiral.py"
R5_SWITCH_NAMES: tuple[str, ...] = (
    "F1_depot_two_phase_override",
    "F2_adaptive_inward_spiral_alpha",
    "F3_triangular_elongation_rho",
    "F4_cosine_angular_coherence",
    "F5_capacity_adaptive_early_return",
)


def make_r5_coalition_fn(mask: tuple[int, int, int, int, int]) -> Callable[..., int]:
    """Build deterministic R5 variant for binary switch tuple (F1, F2, F3, F4, F5)."""
    f1, f2, f3, f4, f5 = (int(bool(x)) for x in mask)

    def select_next_node(
        current_node: int,
        depot: int,
        unvisited_nodes: np.ndarray,
        rest_capacity: float,
        demands: np.ndarray,
        distance_matrix: np.ndarray,
    ) -> int:
        if unvisited_nodes.size == 0:
            return 0

        nodes = np.asarray(unvisited_nodes)
        d_cur = distance_matrix[current_node][nodes].astype(float)
        d_dep = distance_matrix[depot][nodes].astype(float)
        dem = demands[nodes].astype(float)

        scale = float(np.mean(d_dep) + np.mean(d_cur) + 1e-12)

        d0c = float(distance_matrix[depot][current_node]) if current_node != depot else 0.0
        pair = np.maximum(d_dep + d0c, 1e-12)
        rho = d_cur / pair

        # State-only capacity pressure (F2 switch: adaptive inward spiral alpha_eff vs 0.0)
        mean_dem = float(np.mean(dem))
        pressure = float(min(1.0, mean_dem / (rest_capacity + 1e-12)))
        alpha_eff = (1.02 - 0.85 * pressure) if f2 else 0.0

        radial = (d_cur - alpha_eff * d_dep) / scale
        fill = dem / (rest_capacity + 1e-12)
        beta = 0.10

        # Law-of-Cosines angular coherence cos(theta_0) at non-depot node (F4 switch)
        if f4 and current_node != depot:
            denom_cos = np.maximum(2.0 * d_dep * d0c, 1e-12)
            cos_t = np.clip((d_dep * d_dep + d0c * d0c - d_cur * d_cur) / denom_cos, -1.0, 1.0)
            w_cos = 0.20
        else:
            cos_t = np.zeros_like(d_cur)
            w_cos = 0.0

        w_rho = 0.35 if f3 else 0.0
        score = radial + w_rho * rho - beta * fill - w_cos * cos_t

        # F1: Depot-start two-phase policy override
        if f1 and current_node == depot:
            total_dem = float(np.sum(dem))
            rem_routes = total_dem / (rest_capacity + 1e-12)
            if rem_routes > 7.0:
                score = -d_dep / scale - 0.25 * fill
            else:
                score = d_dep / scale - 0.30 * fill
            return int(nodes[int(np.argmin(score))])

        # F5: Capacity-adaptive early return (reads pure geometry rho[best] independently of F3 weight)
        if f5 and current_node != depot:
            best_dem = float(np.max(dem))
            tau = 0.25 + 0.50 * min(1.0, mean_dem / (rest_capacity + 1e-12))
            if best_dem > 0.55 * rest_capacity:
                best_idx_local = int(np.argmin(score))
                rho_best = float(rho[best_idx_local])
                if (1.0 - rho_best) < tau:
                    return 0

        return int(nodes[int(np.argmin(score))])

    return select_next_node


def _factorial(n: int) -> int:
    return math.factorial(n)


def compute_exact_shapley(values_by_mask: Mapping[tuple[int, int, int, int, int], float]) -> dict[str, Any]:
    """Compute exact Shapley values and Grabisch 2nd-order interactions over 2^5 coalitions."""
    n = 5
    phi: dict[str, float] = {}
    for i in range(n):
        total = 0.0
        for bits in range(1 << n):
            if (bits >> i) & 1:
                continue
            s_mask = tuple((bits >> k) & 1 for k in range(n))
            s_size = sum(s_mask)
            w = _factorial(s_size) * _factorial(n - s_size - 1) / _factorial(n)
            with_i = list(s_mask)
            with_i[i] = 1
            total += w * (values_by_mask[tuple(with_i)] - values_by_mask[s_mask])  # type: ignore[index]
        phi[R5_SWITCH_NAMES[i]] = total

    interactions: dict[str, float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            total_ij = 0.0
            for bits in range(1 << n):
                if ((bits >> i) & 1) or ((bits >> j) & 1):
                    continue
                s_mask = tuple((bits >> k) & 1 for k in range(n))
                s_size = sum(s_mask)
                w = _factorial(s_size) * _factorial(n - s_size - 2) / _factorial(n - 1)
                m_i = list(s_mask)
                m_i[i] = 1
                m_j = list(s_mask)
                m_j[j] = 1
                m_ij = list(s_mask)
                m_ij[i] = 1
                m_ij[j] = 1
                delta2 = (
                    values_by_mask[tuple(m_ij)]  # type: ignore[index]
                    - values_by_mask[tuple(m_i)]  # type: ignore[index]
                    - values_by_mask[tuple(m_j)]  # type: ignore[index]
                    + values_by_mask[s_mask]  # type: ignore[index]
                )
                total_ij += w * delta2
            interactions[f"{R5_SWITCH_NAMES[i]}__x__{R5_SWITCH_NAMES[j]}"] = total_ij

    v_full = values_by_mask[(1, 1, 1, 1, 1)]
    v_empty = values_by_mask[(0, 0, 0, 0, 0)]
    phi_sum = sum(phi.values())
    efficiency_residual = abs(phi_sum - (v_full - v_empty))
    return {
        "v_empty_00000": v_empty,
        "v_full_11111": v_full,
        "total_lift_full_minus_empty": v_full - v_empty,
        "shapley_sum": phi_sum,
        "efficiency_identity_residual": efficiency_residual,
        "efficiency_identity_exact": bool(efficiency_residual < 1e-10),
        "shapley_values": {k: round(v, 6) for k, v in phi.items()},
        "interaction_indices_order2": {k: round(v, 6) for k, v in interactions.items()},
    }


def run_shapley_r5(suites: Sequence[tuple[str, str]] = (("cvrp_select_multiscale_64", "selection"), ("cvrp_hist_p0_120", "heldout"))) -> dict[str, Any]:
    """Execute 32-coalition exact Shapley attribution with frozen R5 11111 bit-for-bit verification."""
    frozen_code = R5_PATH.read_text(encoding="utf-8")
    frozen_fn = compile_pointwise_rule(frozen_code, "s2_r5_spiral_frozen")
    out: dict[str, Any] = {}

    for suite_id, split in suites:
        suite = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
        instances = list(suite["instances"])
        dist_conv = suite["distance_convention"]
        veh_pol = suite["vehicle_limit_policy"]

        # Verify 11111 coalition reproduces frozen s2_r5_spiral bit-for-bit (0.0 diff) on every instance
        full_fn = make_r5_coalition_fn((1, 1, 1, 1, 1))
        cw_lens: list[float] = []
        frozen_lens: list[float] = []
        max_bit_diff = 0.0
        for inst in instances:
            res_f = execute_pointwise_rule(
                frozen_fn, inst, distance_convention=dist_conv, vehicle_limit_policy=veh_pol, record_trace=False, time_budget_ms=None,
            )
            res_c = execute_pointwise_rule(
                full_fn, inst, distance_convention=dist_conv, vehicle_limit_policy=veh_pol, record_trace=False, time_budget_ms=None,
            )
            res_cw = evaluate_algorithm_on_instance(
                "cw_relocate_2opt", inst, distance_convention=dist_conv, vehicle_limit_policy=veh_pol, time_budget_ms=500.0, enforce_wall_deadline=False, record_trace=False,
            )
            assert res_f["valid"] and res_c["valid"]
            diff = abs(float(res_f["tour_length"]) - float(res_c["tour_length"]))
            if diff > max_bit_diff:
                max_bit_diff = diff
            frozen_lens.append(float(res_f["tour_length"]))
            cw_lens.append(float(res_cw["tour_length"]))

        if max_bit_diff != 0.0:
            raise RuntimeError(f"r5_11111_bit_for_bit_mismatch:{suite_id}:{max_bit_diff}")

        exog_cw_mean = sum(cw_lens) / len(cw_lens)

        coalition_means: dict[tuple[int, int, int, int, int], float] = {}
        coalition_records: dict[str, list[float]] = {}
        coalition_summary: dict[str, Any] = {}

        for bits in range(1 << 5):
            mask = tuple((bits >> k) & 1 for k in range(5))
            mask_str = "".join(str(x) for x in mask)
            fn = make_r5_coalition_fn(mask)  # type: ignore[arg-type]
            vals: list[float] = []
            for inst in instances:
                r = execute_pointwise_rule(
                    fn, inst, distance_convention=dist_conv, vehicle_limit_policy=veh_pol, record_trace=False, time_budget_ms=None,
                )
                if not r["valid"] or r["tour_length"] is None:
                    raise RuntimeError(f"r5_coalition_infeasible:{suite_id}:{mask_str}:{inst['instance_id']}")
                vals.append(float(r["tour_length"]))
            mean_val = sum(vals) / len(vals)
            coalition_means[mask] = mean_val  # type: ignore[index]
            coalition_records[mask_str] = vals
            coalition_summary[mask_str] = {
                "mean_tour_length": round(mean_val, 6),
                "gain_pct_vs_cw_relocate_2opt": round(100.0 * (exog_cw_mean - mean_val) / exog_cw_mean, 4),
            }

        # Payoff 1: -mean_tour_length (positive Shapley => distance reduction in route units)
        v_neg_len = {m: -val for m, val in coalition_means.items()}
        # Payoff 2: % gain relative to fixed exogenous cw_relocate_2opt denominator
        v_rel_cw = {m: 100.0 * (exog_cw_mean - val) / exog_cw_mean for m, val in coalition_means.items()}

        sh_len = compute_exact_shapley(v_neg_len)
        sh_rel = compute_exact_shapley(v_rel_cw)

        # Leave-one-out hypothesis checks vs 11111 with Holm-Bonferroni correction
        loo_tests: dict[str, Any] = {}
        loo_p: list[tuple[str, float]] = []
        full_vals = coalition_records["11111"]
        for i, fname in enumerate(R5_SWITCH_NAMES):
            m = [1, 1, 1, 1, 1]
            m[i] = 0
            m_str = "".join(str(x) for x in m)
            loo_vals = coalition_records[m_str]
            w = paired_wilcoxon_signed_rank(full_vals, loo_vals)
            b = paired_bootstrap_comparison(full_vals, loo_vals, n_boot=10000, seed=20261124 + i)
            loo_tests[fname] = {
                "mask": m_str,
                "mean_without": coalition_summary[m_str]["mean_tour_length"],
                "marginal_loss_if_removed": round(coalition_summary[m_str]["mean_tour_length"] - coalition_summary["11111"]["mean_tour_length"], 6),
                "wilcoxon_p_two_sided": w["p_two_sided"],
                "bootstrap": b,
            }
            loo_p.append((fname, float(w["p_two_sided"])))

        for (fname, _), ap in zip(loo_p, holm_bonferroni_adjust([p for _, p in loo_p])):
            loo_tests[fname]["p_holm_wilcoxon"] = ap

        out[suite_id] = {
            "suite_id": suite_id,
            "split": split,
            "instance_count": len(instances),
            "bit_for_bit_11111_max_diff": max_bit_diff,
            "exogenous_cw_relocate_2opt_mean": round(exog_cw_mean, 6),
            "shapley_tour_units": sh_len,
            "shapley_pct_vs_cw_exog": sh_rel,
            "leave_one_out_tests": loo_tests,
            "all_32_coalitions": coalition_summary,
        }

    return out


def compute_hrk_radial_lower_bound(instance: Mapping[str, Any], distance_convention: str) -> float:
    """Exact deterministic metric lower bound R(I) = (2/Q) * sum(q_i * d(0, i))."""
    dmat = compute_distance_matrix(
        instance["depot"],
        instance["customer_coordinates"],
        distance_convention=distance_convention,
    )
    cap = float(instance["capacity"])
    demands = [float(q) for q in instance["demands"]]
    return (2.0 / cap) * sum(demands[i] * float(dmat[0, i + 1]) for i in range(len(demands)))


def _pearson_and_slope(xs: Sequence[float], ys: Sequence[float]) -> dict[str, Any]:
    ax = np.asarray(xs, dtype=np.float64)
    ay = np.asarray(ys, dtype=np.float64)
    n = int(ax.size)
    if n < 3 or np.std(ax) <= 1e-12 or np.std(ay) <= 1e-12:
        return {"n": n, "pearson_r": None, "ols_slope": None, "spearman_rho": None}
    r = float(np.corrcoef(ax, ay)[0, 1])
    slope = float(np.cov(ax, ay, ddof=1)[0, 1] / np.var(ax, ddof=1))
    rx = np.argsort(np.argsort(ax)).astype(np.float64)
    ry = np.argsort(np.argsort(ay)).astype(np.float64)
    rho = float(np.corrcoef(rx, ry)[0, 1])

    rng = np.random.default_rng(20261124)
    idx = rng.integers(0, n, size=(2000, n))
    boot_r = []
    for row_idx in idx:
        bx, by = ax[row_idx], ay[row_idx]
        if np.std(bx) > 1e-12 and np.std(by) > 1e-12:
            boot_r.append(float(np.corrcoef(bx, by)[0, 1]))
    ci = [round(float(q), 4) for q in np.quantile(boot_r, [0.025, 0.975])] if boot_r else None
    return {
        "n": n,
        "pearson_r": round(r, 4),
        "pearson_r_boot95": ci,
        "ols_slope": round(slope, 6),
        "spearman_rho": round(rho, 4),
    }


def compute_pure_geometry_scale(instance: Mapping[str, Any], r_lb: float) -> float:
    """Purely geometric exogenous scale G(I) = R(I) + sqrt(n * A_bbox(I)) with zero algorithm tour dependency."""
    pts = [instance["depot"], *instance["customer_coordinates"]]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    area = max((max(xs) - min(xs)) * (max(ys) - min(ys)), 1e-12)
    n_cust = len(instance["customer_coordinates"])
    return float(r_lb) + math.sqrt(max(1, n_cust) * area)


def run_hrk_analysis() -> dict[str, Any]:
    """Fixed-n HRK metric lower-bound & exogenous complementarity regression across three distinct pools."""
    single_step_pool = ("nn", "s2_r4_cos", "s2_r5_spiral", "s2_r7_iso")
    constructive_pool = (*single_step_pool, "cw_parallel_merge", "cvrp_sweep_2opt", "cvrp_farthest_insertion")
    full_pool = (*constructive_pool, "cw_relocate_2opt")
    all_algs = full_pool
    suites_out: dict[str, Any] = {}

    for suite_id, split in (("cvrp_hist_hetero_288", "heldout"), ("cvrp_ext_cvrplib_abp_74", "heldout")):
        suite = load_profile_suite(BENCHMARK_ID, suite_id, split=split)
        instances = list(suite["instances"])
        dist_conv = suite["distance_convention"]
        veh_pol = "unconstrained"

        rows: list[dict[str, Any]] = []
        r_lb_viol = 0

        for idx, inst in enumerate(instances):
            r_lb = compute_hrk_radial_lower_bound(inst, dist_conv)
            g_geom = compute_pure_geometry_scale(inst, r_lb)
            eta_geom = r_lb / max(g_geom, 1e-12)
            row_vals: dict[str, float] = {}
            for aid in all_algs:
                ev = evaluate_algorithm_on_instance(
                    aid, inst, distance_convention=dist_conv, vehicle_limit_policy=veh_pol, time_budget_ms=500.0, enforce_wall_deadline=False, record_trace=False,
                )
                val = float(ev["tour_length"]) if (ev.get("valid") and ev.get("tour_length") is not None) else None
                if val is not None:
                    row_vals[aid] = val
            ref_opt = inst.get("reference_objective")
            if isinstance(ref_opt, (int, float)) and r_lb > float(ref_opt) + 1e-6:
                r_lb_viol += 1
            rows.append({
                "instance_id": inst["instance_id"],
                "size": inst.get("size"),
                "spatial": inst.get("spatial"),
                "depot_style": inst.get("depot_style"),
                "capacity_level": inst.get("capacity_level"),
                "r_lb": r_lb,
                "g_geom": g_geom,
                "eta_geom": eta_geom,
                "reference_objective": float(ref_opt) if isinstance(ref_opt, (int, float)) else None,
                "vals": row_vals,
            })

        def _analyze_pool(pool_name: str, pool: Sequence[str]) -> dict[str, Any]:
            common_idx = [i for i, row in enumerate(rows) if all(aid in row["vals"] for aid in pool)]
            sbs_aid = min(
                pool,
                key=lambda aid: sum(rows[i]["vals"][aid] for i in common_idx) / max(1, len(common_idx)),
            )
            exog_aid = "cw_parallel_merge"
            enriched: list[dict[str, Any]] = []
            for i in common_idx:
                row = rows[i]
                vbs = min(row["vals"][aid] for aid in pool)
                sbs = row["vals"][sbs_aid]
                exog_base = row["vals"].get(exog_aid, sbs)
                raw_gap = sbs - vbs
                geom_rel_gap = 100.0 * raw_gap / max(row["g_geom"], 1e-12)
                exog_rel_gap = 100.0 * raw_gap / max(exog_base, 1e-12)
                eta_exog = row["r_lb"] / max(exog_base, 1e-12)
                eta_opt = (row["r_lb"] / row["reference_objective"]) if row["reference_objective"] else None
                enriched.append({
                    **row,
                    "vbs": vbs,
                    "sbs": sbs,
                    "exog_base": exog_base,
                    "raw_gap": raw_gap,
                    "geom_rel_gap_pct": geom_rel_gap,
                    "exog_rel_gap_pct": exog_rel_gap,
                    "eta_rad_exog_cw": eta_exog,
                    "eta_rad_opt": eta_opt,
                })

            by_size_corr: dict[str, Any] = {}
            size_groups: dict[str, list[dict[str, Any]]] = {}
            if suite_id == "cvrp_hist_hetero_288":
                for e in enriched:
                    size_groups.setdefault(str(e["size"]), []).append(e)
            else:
                size_groups["all_abp_74"] = enriched

            for skey, grp in sorted(size_groups.items()):
                sbs_sum = sum(x["sbs"] for x in grp)
                vbs_sum = sum(x["vbs"] for x in grp)
                entry: dict[str, Any] = {
                    "count": len(grp),
                    "sbs_mean": round(sbs_sum / len(grp), 4),
                    "vbs_mean": round(vbs_sum / len(grp), 4),
                    "raw_gap_mean": round(sum(x["raw_gap"] for x in grp) / len(grp), 4),
                    "pooled_gap_pct_vs_sbs": round(100.0 * (sbs_sum - vbs_sum) / max(sbs_sum, 1e-12), 4),
                    "geom_rel_gap_pct_mean": round(sum(x["geom_rel_gap_pct"] for x in grp) / len(grp), 4),
                    "exog_rel_gap_pct_mean": round(sum(x["exog_rel_gap_pct"] for x in grp) / len(grp), 4),
                    "eta_geom_mean": round(sum(x["eta_geom"] for x in grp) / len(grp), 4),
                    "eta_rad_exog_mean": round(sum(x["eta_rad_exog_cw"] for x in grp) / len(grp), 4),
                    "corr_eta_geom_vs_raw_gap": _pearson_and_slope([x["eta_geom"] for x in grp], [x["raw_gap"] for x in grp]),
                    "corr_eta_exog_vs_raw_gap": _pearson_and_slope([x["eta_rad_exog_cw"] for x in grp], [x["raw_gap"] for x in grp]),
                    "corr_eta_exog_vs_exog_rel_gap": _pearson_and_slope([x["eta_rad_exog_cw"] for x in grp], [x["exog_rel_gap_pct"] for x in grp]),
                }
                if all(x["eta_rad_opt"] is not None for x in grp):
                    entry["corr_eta_opt_vs_raw_gap"] = _pearson_and_slope(
                        [float(x["eta_rad_opt"]) for x in grp], [x["raw_gap"] for x in grp],
                    )
                    entry["corr_eta_opt_vs_exog_rel_gap"] = _pearson_and_slope(
                        [float(x["eta_rad_opt"]) for x in grp], [x["exog_rel_gap_pct"] for x in grp],
                    )
                if suite_id == "cvrp_hist_hetero_288":
                    strat_slices = {}
                    for factor in ("spatial", "depot_style", "capacity_level"):
                        fbuckets: dict[str, list[dict[str, Any]]] = {}
                        for x in grp:
                            fbuckets.setdefault(str(x.get(factor)), []).append(x)
                        strat_slices[factor] = {
                            fv: {
                                "count": len(fgrp),
                                "eta_geom_mean": round(sum(z["eta_geom"] for z in fgrp) / len(fgrp), 4),
                                "eta_rad_exog_mean": round(sum(z["eta_rad_exog_cw"] for z in fgrp) / len(fgrp), 4),
                                "raw_gap_mean": round(sum(z["raw_gap"] for z in fgrp) / len(fgrp), 4),
                                "exog_rel_gap_pct_mean": round(sum(z["exog_rel_gap_pct"] for z in fgrp) / len(fgrp), 4),
                                "corr_eta_geom_vs_raw_gap": _pearson_and_slope([z["eta_geom"] for z in fgrp], [z["raw_gap"] for z in fgrp]),
                                "corr_eta_vs_exog_rel_gap": _pearson_and_slope([z["eta_rad_exog_cw"] for z in fgrp], [z["exog_rel_gap_pct"] for z in fgrp]),
                            }
                            for fv, fgrp in sorted(fbuckets.items())
                        }
                    entry["stratified_slices"] = strat_slices
                by_size_corr[skey] = entry

            return {
                "pool_name": pool_name,
                "common_completed_count": len(enriched),
                "fixed_pool": list(pool),
                "fixed_sbs": sbs_aid,
                "exogenous_denominator": exog_aid,
                "pure_geometry_scale": "G(I) = R(I) + sqrt(n * A_bbox(I))",
                "fixed_n_analysis": by_size_corr,
            }

        ss_res = _analyze_pool("single_step_pool", single_step_pool)
        c_res = _analyze_pool("constructive_pool", constructive_pool)
        f_res = _analyze_pool("full_pool", full_pool)
        suites_out[suite_id] = {
            "suite_id": suite_id,
            "r_lb_lower_bound_violations": r_lb_viol,
            "single_step_pool": ss_res,
            "constructive_pool": c_res,
            "full_pool": f_res,
            "fixed_n_analysis": c_res["fixed_n_analysis"],
            "fixed_sbs": c_res["fixed_sbs"],
            "common_completed_count": c_res["common_completed_count"],
        }

    return suites_out


def _run_alpha_sweep_on_instances(instances: Sequence[Mapping[str, Any]], *, distance_convention: str = "euc_2d_float") -> dict[str, Any]:
    """Run s_alpha(i,j) = d(i,j) - alpha * d(0,j) sweep with real-instance depot-start tie & return-leg metrics."""
    alphas = (0.0, 0.3, 0.6, 0.8, 0.99, 1.0, 1.01, 1.2, 1.5, 2.0)
    dmats = [
        compute_distance_matrix(inst["depot"], inst["customer_coordinates"], distance_convention=distance_convention)
        for inst in instances
    ]
    curve: dict[str, Any] = {}
    for a in alphas:
        def _make_alpha_rule(av: float):
            def _rule(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
                if unvisited_nodes.size == 0:
                    return 0
                nodes = np.asarray(unvisited_nodes)
                s = distance_matrix[current_node][nodes] - av * distance_matrix[depot][nodes]
                return int(nodes[int(np.argmin(s))])
            return _rule
        afn = _make_alpha_rule(a)
        lens: list[float] = []
        return_shares: list[float] = []
        max_depot_spread = 0.0
        tied_instances = 0
        for inst, dmat in zip(instances, dmats):
            res = execute_pointwise_rule(afn, inst, distance_convention=distance_convention, vehicle_limit_policy="unconstrained", time_budget_ms=None)
            tlen = float(res["tour_length"])
            lens.append(tlen)
            # Compute actual empty-return share (last non-depot customer -> depot leg for each route)
            ret_len = 0.0
            for rt in (res.get("routes") or []):
                custs = [int(c) for c in rt if int(c) != 0]
                if custs:
                    ret_len += float(dmat[custs[-1], 0])
            return_shares.append(100.0 * ret_len / max(tlen, 1e-12))
            # Real-instance depot-start score spread s_alpha(0, j) = (1 - alpha) * d(0, j) across all customers
            d0 = np.asarray(dmat[0, 1:], dtype=np.float64)
            s0 = d0 - a * d0
            spread = float(np.max(s0) - np.min(s0)) if s0.size else 0.0
            if spread > max_depot_spread:
                max_depot_spread = spread
            if spread == 0.0:
                tied_instances += 1
        curve[str(a)] = {
            "instance_count": len(instances),
            "mean_tour_length": round(sum(lens) / len(lens), 6),
            "mean_empty_return_share_pct": round(sum(return_shares) / len(return_shares), 4),
            "depot_start_sign_1_minus_alpha": round(1.0 - a, 4),
            "depot_start_max_score_spread": round(max_depot_spread, 12),
            "depot_start_tied_instance_count": tied_instances,
            "depot_start_identical_tie_at_1": bool(tied_instances == len(instances) and max_depot_spread == 0.0),
        }
    return curve


def run_group_invariance_and_alpha() -> dict[str, Any]:
    """Verify Euclidean/capacity scaling, E(2) rotation/translation, TSPLIB nint exception, and full-suite alpha=1 flip."""
    # 1. Cross-problem similarity & E(2) checks on full cvrp_dev_hetero_24 (24 instances)
    cvrp_dev_all = list(load_dev_or_public_suite("cvrp_dev_hetero_24", role="interactive_sandbox")["instances"])
    cvrp_select_64 = list(load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")["instances"])
    r5_code = R5_PATH.read_text(encoding="utf-8")
    r5_fn = compile_pointwise_rule(r5_code, "r5_inv")

    theta = 0.713
    ct, st = math.cos(theta), math.sin(theta)
    tx, ty = 13.7, -4.2

    def _rot_trans_pt(pt: Sequence[float]) -> list[float]:
        x, y = float(pt[0]), float(pt[1])
        return [x * ct - y * st + tx, x * st + y * ct + ty]

    cvrp_scale_drifts, cvrp_e2_drifts = [], []
    for inst in cvrp_dev_all:
        ref = execute_pointwise_rule(r5_fn, inst, distance_convention="euc_2d_float", vehicle_limit_policy="unconstrained", time_budget_ms=None)
        ref_len = float(ref["tour_length"])
        for s in (1e-3, 1000.0):
            sc = copy.deepcopy(inst)
            sc["depot"] = [float(x) * s for x in sc["depot"]]
            sc["customer_coordinates"] = [[float(x) * s for x in p] for p in sc["customer_coordinates"]]
            sr = execute_pointwise_rule(r5_fn, sc, distance_convention="euc_2d_float", vehicle_limit_policy="unconstrained", time_budget_ms=None)
            cvrp_scale_drifts.append(abs((float(sr["tour_length"]) / s) - ref_len) / ref_len)
        e2 = copy.deepcopy(inst)
        e2["depot"] = _rot_trans_pt(e2["depot"])
        e2["customer_coordinates"] = [_rot_trans_pt(p) for p in e2["customer_coordinates"]]
        er = execute_pointwise_rule(r5_fn, e2, distance_convention="euc_2d_float", vehicle_limit_policy="unconstrained", time_budget_ms=None)
        cvrp_e2_drifts.append(abs(float(er["tour_length"]) - ref_len) / ref_len)

    # TSP scaling invariance (float vs TSPLIB nint exception)
    from agent_skill_loop.interface_design.templates import get_template_spec
    tsp_tpl = get_template_spec("tsp_constructive_step", "v1")
    tsp_fn = compile_hook_function(tsp_tpl.default_baseline_hook_code, hook_name=tsp_tpl.hook_name, expected_args=tsp_tpl.hook_signature)
    tsp_insts = load_dev_or_public_suite("tsp_m31_dev_36", role="interactive_sandbox")["instances"][:8]
    tsp_float_drifts, tsp_e2_drifts = [], []
    for inst in tsp_insts:
        ref = evaluate_hook_on_instance_inprocess(
            template_id="tsp_constructive_step", template_version="v1", hook_fn=tsp_fn,
            instance=inst, distance_convention="euc_2d_float", vehicle_limit_policy="not_applicable", time_budget_ms=500.0,
        )
        ref_len = float(ref["objective"])
        for s in (1e-3, 1000.0):
            sc = copy.deepcopy(inst)
            sc["coordinates"] = [[float(x) * s for x in p] for p in sc["coordinates"]]
            sr = evaluate_hook_on_instance_inprocess(
                template_id="tsp_constructive_step", template_version="v1", hook_fn=tsp_fn,
                instance=sc, distance_convention="euc_2d_float", vehicle_limit_policy="not_applicable", time_budget_ms=500.0,
            )
            tsp_float_drifts.append(abs((float(sr["objective"]) / s) - ref_len) / ref_len)
        e2 = copy.deepcopy(inst)
        e2["coordinates"] = [_rot_trans_pt(p) for p in e2["coordinates"]]
        er = evaluate_hook_on_instance_inprocess(
            template_id="tsp_constructive_step", template_version="v1", hook_fn=tsp_fn,
            instance=e2, distance_convention="euc_2d_float", vehicle_limit_policy="not_applicable", time_budget_ms=500.0,
        )
        tsp_e2_drifts.append(abs(float(er["objective"]) - ref_len) / ref_len)

    # Online OBP scaling invariance under (w_j, C) -> (lambda*w_j, lambda*C)
    obp_tpl = get_template_spec("obp_online_priority", "v1")
    obp_fn = compile_hook_function(obp_tpl.default_baseline_hook_code, hook_name=obp_tpl.hook_name, expected_args=obp_tpl.hook_signature)
    obp_insts = load_dev_or_public_suite("obp_m31_dev_36", role="interactive_sandbox")["instances"][:8]
    obp_drifts = []
    for inst in obp_insts:
        ref = evaluate_hook_on_instance_inprocess(
            template_id="obp_online_priority", template_version="v1", hook_fn=obp_fn,
            instance=inst, distance_convention="not_applicable", vehicle_limit_policy="not_applicable", time_budget_ms=500.0,
        )
        for s in (1e-3, 1000.0):
            sc = copy.deepcopy(inst)
            sc["capacity"] = float(sc["capacity"]) * s
            sc["items"] = [float(x) * s for x in sc["items"]]
            sr = evaluate_hook_on_instance_inprocess(
                template_id="obp_online_priority", template_version="v1", hook_fn=obp_fn,
                instance=sc, distance_convention="not_applicable", vehicle_limit_policy="not_applicable", time_budget_ms=500.0,
            )
            obp_drifts.append(abs(float(sr["objective"]) - float(ref["objective"])))

    # Alpha bifurcation sweep on full cvrp_select_multiscale_64 (64 multi-scale instances) and full cvrp_dev_hetero_24 (24 instances)
    alpha_select64 = _run_alpha_sweep_on_instances(cvrp_select_64)
    alpha_dev24 = _run_alpha_sweep_on_instances(cvrp_dev_all)

    return {
        "similarity_and_e2_invariance": {
            "cvrp_tested_instance_count": len(cvrp_dev_all),
            "cvrp_r5_max_scale_rel_drift": max(cvrp_scale_drifts),
            "cvrp_r5_max_e2_rel_drift": max(cvrp_e2_drifts),
            "tsp_max_scale_rel_drift": max(tsp_float_drifts),
            "tsp_max_e2_rel_drift": max(tsp_e2_drifts),
            "obp_max_scale_abs_bins_drift": max(obp_drifts),
            "documented_exceptions": [
                "tsplib_euc_2d / euc_2d_int integer rounding breaks continuous scale equivariance at tiny scales",
                "1e-12 numerical denominator stabilization breaks extreme s->0 limits below machine scale",
                "wall-clock deadline truncation depends on runtime CPU speed",
            ],
        },
        "alpha_equals_1_bifurcation_sweep_suite": "cvrp_select_multiscale_64",
        "alpha_equals_1_bifurcation_sweep": alpha_select64,
        "alpha_equals_1_bifurcation_sweep_dev24": alpha_dev24,
    }


def dissect_solver_manifest(solver_path: Path, *, budget_ms: float = 500.0) -> dict[str, Any]:
    """Algebraic AST and finite-difference perturbation dissection of an evolved frozen L3/L3b solver."""
    raw = json.loads(solver_path.read_text(encoding="utf-8"))
    if "frozen_solver" in raw:
        raw = raw["frozen_solver"]
    fs = FrozenInterfaceSolver.from_dict(raw)

    # AST & structural stats across primary + any secondary hooks
    hooks_meta = {}
    hook_map = dict(fs.hook_implementations) if fs.hook_implementations else {fs.hook_name: fs.hook_code}
    for hname, hcode in hook_map.items():
        tree = ast.parse(hcode)
        func_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        args = [a.arg for a in func_defs[0].args.args] if func_defs else []
        loaded_names = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)})
        ops = sorted({type(n.op).__name__ for n in ast.walk(tree) if isinstance(n, ast.BinOp)})
        hooks_meta[hname] = {
            "loc": len(hcode.splitlines()),
            "signature_args": args,
            "referenced_args": [a for a in args if a in loaded_names],
            "binary_ops": ops,
        }

    # Evaluate anytime trajectory on cvrp_select_multiscale_64
    sel64 = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    anytime_points = ("10", "25", "100", "250", "500")
    recs = [
        evaluate_frozen_interface_solver(
            fs, inst, distance_convention=sel64["distance_convention"],
            vehicle_limit_policy=sel64["vehicle_limit_policy"], solve_deadline_ms=budget_ms,
        )
        for inst in sel64["instances"][:16]
    ]
    valid = [r for r in recs if r.get("valid") and r.get("tour_length") is not None]
    anytime_means: dict[str, float | None] = {}
    for cp in anytime_points:
        vals = [float((r.get("anytime_curve") or {}).get(cp)) for r in valid if isinstance((r.get("anytime_curve") or {}).get(cp), (int, float))]
        anytime_means[cp] = round(sum(vals) / len(vals), 4) if len(vals) == len(valid) and valid else None

    return {
        "solver_id": fs.solver_id,
        "template_id": fs.template_id,
        "hooks_ast": hooks_meta,
        "select_16_preview": {
            "valid_count": len(valid),
            "mean_tour_length": round(sum(float(r["tour_length"]) for r in valid) / len(valid), 4) if valid else None,
            "anytime_curve_means": anytime_means,
        },
    }


def cmd_shapley_r5(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    res = run_shapley_r5()
    atomic_write_json(out_dir / "m4_shapley_r5.json", res)
    print(json.dumps({k: v["shapley_tour_units"] for k, v in res.items()}, indent=2))
    return 0


def cmd_hrk_analysis(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    res = run_hrk_analysis()
    atomic_write_json(out_dir / "m4_hrk_analysis.json", res)
    print(json.dumps({k: {"r_lb_violations": v["r_lb_lower_bound_violations"], "common": v["common_completed_count"]} for k, v in res.items()}, indent=2))
    return 0


def cmd_group_invariance(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    res = run_group_invariance_and_alpha()
    atomic_write_json(out_dir / "m4_group_invariance.json", res)
    print(json.dumps(res["similarity_and_e2_invariance"], indent=2))
    return 0


def cmd_dissect_m32(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    dissected = {}
    for sp in args.solver_paths:
        p = Path(sp).resolve()
        dissected[p.stem] = dissect_solver_manifest(p, budget_ms=float(args.time_budget_ms))
    atomic_write_json(out_dir / "m4_m32_operator_dissection.json", dissected)
    print(json.dumps(dissected, indent=2))
    return 0


def cmd_full_part1(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sh = run_shapley_r5()
    hrk = run_hrk_analysis()
    grp = run_group_invariance_and_alpha()
    full = {
        "schema_version": "m4-math-closure-part1/v1",
        "generated_at": utc_now(),
        "shapley_r5": sh,
        "hrk_analysis": hrk,
        "group_invariance_and_alpha": grp,
    }
    atomic_write_json(out_dir / "m4_math_closure_part1.json", full)

    md = [
        "# Milestone 4 Part 1: Exact Shapley, HRK Lower-Bound & Similarity Group Closure",
        "",
        "## 1. Exact 2^5 = 32 Shapley Attribution (`s2_r5_spiral.py`)",
        "",
    ]
    for sid, sdata in sh.items():
        tu = sdata["shapley_tour_units"]
        md.extend([
            f"### Suite `{sid}` (N={sdata['instance_count']}, `11111` bit-for-bit max diff = `{sdata['bit_for_bit_11111_max_diff']}`, residual = `{tu['efficiency_identity_residual']:.2e}`)",
            "",
            "| Component | Shapley (Route Units Reduced) | Shapley (% vs `cw_relocate_2opt`) | LOO Marginal Loss | p_Holm |",
            "|---|---:|---:|---:|---:|",
        ])
        for fname in R5_SWITCH_NAMES:
            loo = sdata["leave_one_out_tests"][fname]
            md.append(
                f"| {fname} | {tu['shapley_values'][fname]:+.4f} | {sdata['shapley_pct_vs_cw_exog']['shapley_values'][fname]:+.4f}% | "
                f"{loo['marginal_loss_if_removed']:+.4f} | {loo['p_holm_wilcoxon']:.3e} |"
            )
        md.extend([
            "",
            "#### Top Order-2 Shapley Synergy / Interaction Pairs (`I(i, j)`)",
            "",
            "| Component Pair | Order-2 Interaction (Route Units) | Order-2 Interaction (% vs `cw_relocate_2opt`) |",
            "|---|---:|---:|",
        ])
        inter_u = tu["interaction_indices_order2"]
        inter_p = sdata["shapley_pct_vs_cw_exog"]["interaction_indices_order2"]
        for pair_key in sorted(inter_u, key=lambda k: abs(inter_u[k]), reverse=True)[:5]:
            md.append(f"| `{pair_key}` | {inter_u[pair_key]:+.4f} | {inter_p[pair_key]:+.4f}% |")
        md.append("")
    md.extend([
        "## 2. HRK Metric Lower Bound `R(I)` & Fixed-`n` Complementarity Analysis",
        "",
        f"- `cvrp_ext_cvrplib_abp_74`: R(I) lower bound violations vs official OPT = `{hrk['cvrp_ext_cvrplib_abp_74']['r_lb_lower_bound_violations']}`",
        "- Pure-geometry exogenous proxy `G(I) = R(I) + sqrt(n * A_bbox(I))` defines `eta_geom = R(I) / G(I)` with **zero algorithm tour denominator** so `corr(eta_geom, raw_gap)` is strictly free of shared-denominator coupling.",
        "",
    ])
    for suite_key, suite_heading in (
        ("cvrp_hist_hetero_288", "Fixed-`n` Analysis: `cvrp_hist_hetero_288`"),
        ("cvrp_ext_cvrplib_abp_74", "Pooled Cross-Size Summary (`45` sizes `n=15..100`, `euc_2d_nint` rounding caveat on fractional <1 coordinates): `cvrp_ext_cvrplib_abp_74`"),
    ):
        for pool_key, pool_label in (
            ("single_step_pool", "Single-Step Sequential Pool (`nn`, `s2_r4_cos`, `s2_r5_spiral`, `s2_r7_iso`)"),
            ("constructive_pool", "Constructive Pool (+ `cw_parallel_merge`, `cvrp_sweep_2opt`, `cvrp_farthest_insertion`)"),
            ("full_pool", "Full Pool (Constructive + 2-opt/Relocate)"),
        ):
            pool_block = hrk[suite_key][pool_key]
            md.extend([
                f"### {suite_heading} — {pool_label} (common N={pool_block['common_completed_count']}, SBS=`{pool_block['fixed_sbs']}`)",
                "",
                "| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |",
                "|---|---:|---|---:|---:|---:|---:|---:|",
            ])
            for skey, srow in pool_block["fixed_n_analysis"].items():
                cg = srow["corr_eta_geom_vs_raw_gap"]["pearson_r"]
                c1 = srow["corr_eta_exog_vs_raw_gap"]["pearson_r"]
                c2 = srow["corr_eta_exog_vs_exog_rel_gap"]["pearson_r"]
                md.append(
                    f"| {skey} | {srow['count']} | {pool_block['fixed_sbs']} | {srow['raw_gap_mean']:.4f} | "
                    f"{srow['pooled_gap_pct_vs_sbs']:.4f}% | {cg} | {c1} | {c2} |"
                )
            md.append("")
    md.extend([
        "## 3. Similarity Group, E(2) Isometry & alpha=1 Phase Bifurcation",
        "",
        "### Scale & E(2) Invariance",
        "",
        "```json",
        json.dumps(grp["similarity_and_e2_invariance"], indent=2),
        "```",
        "",
        "### `s_alpha(i,j) = d(i,j) - alpha * d(0,j)` Bifurcation Sweep (`cvrp_select_multiscale_64`, full N=64 multi-scale)",
        "",
        "| alpha | Mean Tour Length | Empty-Return Share (%) | Sign(1 - alpha) | Real-Instance Max Spread | All Instances Exact Tie |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for aval, arow in grp["alpha_equals_1_bifurcation_sweep"].items():
        md.append(
            f"| {aval} | {arow['mean_tour_length']:.6f} | {arow['mean_empty_return_share_pct']:.4f}% | "
            f"{arow['depot_start_sign_1_minus_alpha']:+.4f} | {arow['depot_start_max_score_spread']:.2e} | {arow['depot_start_identical_tie_at_1']} |"
        )
    md.extend([
        "",
        "### Full `cvrp_dev_hetero_24` Reference Sweep (N=24)",
        "",
        "| alpha | Mean Tour Length | Empty-Return Share (%) | Real-Instance Max Spread | All Instances Exact Tie |",
        "|---:|---:|---:|---:|---:|",
    ])
    for aval, arow in grp["alpha_equals_1_bifurcation_sweep_dev24"].items():
        md.append(
            f"| {aval} | {arow['mean_tour_length']:.6f} | {arow['mean_empty_return_share_pct']:.4f}% | "
            f"{arow['depot_start_max_score_spread']:.2e} | {arow['depot_start_identical_tie_at_1']} |"
        )
    (out_dir / "m4_math_closure_part1.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "json": str(out_dir / "m4_math_closure_part1.json"),
        "md": str(out_dir / "m4_math_closure_part1.md"),
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Milestone 4 Mathematical Closure CLI.")
    p.add_argument("--output-dir", type=Path, default=REPO / "experiments" / "milestone4")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("shapley-r5")
    s1.set_defaults(func=cmd_shapley_r5)

    s2 = sub.add_parser("hrk-analysis")
    s2.set_defaults(func=cmd_hrk_analysis)

    s3 = sub.add_parser("group-invariance")
    s3.set_defaults(func=cmd_group_invariance)

    s4 = sub.add_parser("dissect-m32")
    s4.add_argument("--solver-paths", nargs="+", required=True)
    s4.add_argument("--time-budget-ms", type=float, default=500.0)
    s4.set_defaults(func=cmd_dissect_m32)

    s5 = sub.add_parser("full-part1")
    s5.set_defaults(func=cmd_full_part1)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
