"""Wave 1 (0-API-cost) offline clean audit & no-contention re-evaluation.

Implements A1-A4 under ``experiments/milestone6_wave1_clean_audit/`` without
mutating any historical artifacts, custody files, or published releases:
  - A1: Clean ``baselines_2026`` audit (fixing 6 uncensored overrun leaks and
        separating 5,101 PyVRP anytime-callback vs strict-return rows).
  - A2: Strict ``completed_before_deadline`` re-aggregation for M2 & M3 blind
        suites (500ms & 25ms) with dual denominators and quadrant decomposition.
  - A3: M3.2 ``2x2`` (train_timeout x eval_timeout) orthogonal evaluation on
        ``cvrp_m32_blind_120`` and external 430 instances under single-worker mode.
  - A4: Single-worker no-contention 430-instance benchmark across 23 stage
        representatives + A1 external baselines + concurrency jitter comparison.
"""

from __future__ import annotations

import argparse
from collections import Counter
import datetime as _dt
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Callable, Mapping, Sequence

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.baselines_2026 import dual_timing_fields, summarize_solve_timing
from agent_skill_loop.cvrp_workbench.solvers import SOLVER_CATALOG, evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.blind_eval import (
    BLIND_COMMITMENT_PATH,
    TIGHT_SOLVER_IDS,
    paired_bootstrap_comparison,
    unseal_and_verify_m2_blind_suite,
)
from agent_skill_loop.interface_design.blind_eval_m3 import (
    M3_EXTRA_L3_SOLVER_ID,
    PHASE3C_SEEDS,
    holm_bonferroni_adjust,
)
from agent_skill_loop.interface_design.blind_eval_m32 import (
    M32_BLIND_COMMITMENT_PATH,
    M32_SEEDS,
    read_verified_milestone_blind_payload,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from tools.run_b4_intron_ablation import (
    build_pruned_m32_champion,
    load_m32_champion_solver,
    load_raw_m32_champion,
)
from tools.run_external_baselines_2026 import _score as _baselines_score
from tools.run_external_baselines_2026 import _summary as _baselines_summary


DEFAULT_OUT_DIR = _REPO / "experiments" / "milestone6_wave1_clean_audit"
EXTERNAL_SUITES: tuple[str, ...] = (
    "cvrp_ext_eohs_256",
    "cvrp_ext_cvrplib_abp_74",
    "cvrp_ext_cvrplib_x_100",
)
TRUE_OR_SUITES: tuple[str, ...] = ("cvrp_ext_cvrplib_abp_74", "cvrp_ext_cvrplib_x_100")
FORBIDDEN_LEAK_KEYS: frozenset[str] = frozenset({
    "sealed_seed_token",
    "seed_token",
    "depot",
    "coordinates",
    "customer_coordinates",
    "demands",
    "items",
    "item_sizes",
})


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def assert_no_blind_leakage(node: Any, path: str = "$") -> None:
    """Recursively verify that no raw blind coordinates, demands, or seed tokens exist."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key) in FORBIDDEN_LEAK_KEYS:
                raise ValueError(f"forbidden_blind_key_detected:{path}.{key}")
            assert_no_blind_leakage(value, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            assert_no_blind_leakage(item, f"{path}[{idx}]")


def _write_clean_json(path: Path, payload: Mapping[str, Any]) -> None:
    assert_no_blind_leakage(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def compute_quadrant_decomposition(
    cand_completed: Sequence[bool],
    cand_scored: Sequence[float],
    base_completed: Sequence[bool],
    base_scored: Sequence[float],
    references: Sequence[float],
) -> dict[str, Any]:
    """Exact Proposition 1 four-quadrant decomposition of overall penalized score delta.

    Positive gain means ``cand`` has LOWER scored cost than ``base``.
    """
    if not (len(cand_completed) == len(cand_scored) == len(base_completed) == len(base_scored) == len(references)):
        raise ValueError("quadrant_length_mismatch")
    n = len(cand_completed)
    both_gain = 0.0
    cand_only_gain = 0.0
    base_only_gain = 0.0
    both_pen_gain = 0.0
    counts = {"both_completed": 0, "cand_only_completed": 0, "base_only_completed": 0, "both_penalized": 0}
    total_base = 0.0
    total_cand = 0.0

    for cc, cs, bc, bs, ref in zip(cand_completed, cand_scored, base_completed, base_scored, references, strict=True):
        total_cand += float(cs)
        total_base += float(bs)
        diff = float(bs) - float(cs)
        if cc and bc:
            counts["both_completed"] += 1
            both_gain += diff
        elif cc and not bc:
            counts["cand_only_completed"] += 1
            # Validate penalty parity when ref is positive
            cand_only_gain += diff
        elif not cc and bc:
            counts["base_only_completed"] += 1
            base_only_gain += diff
        else:
            counts["both_penalized"] += 1
            both_pen_gain += diff

    sum_parts = both_gain + cand_only_gain + base_only_gain + both_pen_gain
    exact_diff = total_base - total_cand
    residual = abs(sum_parts - exact_diff)
    return {
        "n_instances": n,
        "counts": counts,
        "base_minus_cand_total": round(exact_diff, 6),
        "both_completed_total_gain": round(both_gain, 6),
        "cand_only_completed_total_gain": round(cand_only_gain, 6),
        "base_only_completed_total_gain": round(base_only_gain, 6),
        "both_penalized_total_gain": round(both_pen_gain, 6),
        "mean_overall_gain": round(exact_diff / n, 6) if n else 0.0,
        "mean_both_completed_contribution": round(both_gain / n, 6) if n else 0.0,
        "mean_completion_divergence_contribution": round((cand_only_gain + base_only_gain) / n, 6) if n else 0.0,
        "rel_overall_gain_pct": round(100.0 * exact_diff / max(total_base, 1e-12), 4),
        "identity_residual": float(residual),
    }


def is_strict_completed_before_deadline(rec: Mapping[str, Any], *, budget_ms: float | None = None) -> bool:
    """Strict completion rule excluding ``budget_exhausted`` truncations and uncensored deadline overruns."""
    obj = rec.get("tour_length", rec.get("objective"))
    if rec.get("status") != "ok" or rec.get("valid") is not True or obj is None:
        return False
    if rec.get("budget_exhausted") is True or rec.get("time_limit_reached") is True:
        return False
    b_ms = float(budget_ms if budget_ms is not None else (rec.get("budget_ms") or 0.0))
    solve_ms = rec.get("solve_ms")
    if not rec.get("solve_censored") and b_ms > 0.0 and isinstance(solve_ms, (int, float)) and float(solve_ms) > b_ms:
        return False
    return True


def _paired_contrast(
    cand_rows: Sequence[Mapping[str, Any]],
    base_rows: Sequence[Mapping[str, Any]],
    *,
    seed: int = 20261124,
    bootstrap_samples: int = 10000,
) -> dict[str, Any]:
    """Compute dual-denominator (overall + common_completed) paired stats and quadrant decomposition."""
    cand_comp = [bool(r["completed"]) for r in cand_rows]
    cand_score = [float(r["scored_objective"]) for r in cand_rows]
    base_comp = [bool(r["completed"]) for r in base_rows]
    base_score = [float(r["scored_objective"]) for r in base_rows]
    refs = [float(r["reference_objective"]) for r in cand_rows]

    overall = paired_bootstrap_comparison(cand_score, base_score, n_boot=bootstrap_samples, seed=seed)
    common_idx = [i for i in range(len(cand_rows)) if cand_comp[i] and base_comp[i]]
    if common_idx:
        common = paired_bootstrap_comparison(
            [cand_score[i] for i in common_idx],
            [base_score[i] for i in common_idx],
            n_boot=bootstrap_samples,
            seed=seed,
        )
    else:
        common = {"n_instances": 0, "wilcoxon_signed_rank": None}
    quadrant = compute_quadrant_decomposition(cand_comp, cand_score, base_comp, base_score, refs)
    return {
        "overall": overall,
        "common_completed": common,
        "quadrant_decomposition": quadrant,
    }


def _apply_holm_to_contrasts(contrasts: Mapping[str, dict[str, Any]], *, section: str) -> None:
    """In-place Holm-Bonferroni correction over ``overall`` or ``common_completed`` within a dict."""
    keys = [k for k, v in contrasts.items() if v.get(section, {}).get("wilcoxon_signed_rank") is not None]
    if not keys:
        return
    raw_p = [float(contrasts[k][section]["wilcoxon_signed_rank"]["p_two_sided"]) for k in keys]
    adj_p = holm_bonferroni_adjust(raw_p)
    for k, p_adj in zip(keys, adj_p, strict=True):
        contrasts[k][section]["p_holm_wilcoxon"] = p_adj
        contrasts[k][section]["significant_holm_0_05"] = bool(p_adj < 0.05)


# =============================================================================
# Part A1: baselines_2026 clean audit
# =============================================================================


def reevaluate_baselines_row(row: Mapping[str, Any], *, budget_ms: float, mode: str) -> dict[str, Any]:
    """Re-score a historical baselines_2026 row under clean ``_score`` semantics.

    ``mode``:
      - ``anytime_feasible_before_deadline``: penalize uncensored overruns, keep censored PyVRP incumbents.
      - ``strict_returned_before_deadline``: additionally require ``returned_before_deadline is True``.
    """
    synthetic_inst = {
        "instance_id": row["instance_id"],
        "size": row.get("size", 0),
        "demands": [],
        "reference_objective": row["reference_objective"],
        "reference_kind": row.get("reference_kind"),
        "k_vehicles": row.get("target_vehicles"),
        "exact_k_target_source": row.get("exact_k_target_source"),
    }
    res_like = {
        "tour_length": row.get("tour_length"),
        "objective": row.get("objective"),
        "tour_length_euc_2d_float": row.get("tour_length_euc_2d_float"),
        "valid": row.get("valid"),
        "exact_vehicle_count": row.get("exact_vehicle_count"),
        "within_vehicle_limit": row.get("within_vehicle_limit"),
        "route_count": row.get("route_count"),
        "status": row.get("status"),
        "outcome_class": row.get("outcome_class"),
        "error_code": row.get("error_code"),
        "stop_reason": row.get("stop_reason"),
        "budget_exhausted": row.get("budget_exhausted"),
        "time_limit_reached": row.get("time_limit_reached"),
        "timeout_kind": row.get("timeout_kind"),
        "preprocess_ms": row.get("preprocess_ms"),
        "solve_ms": row.get("solve_ms"),
        "verify_ms": row.get("verify_ms"),
        "deadline_overrun_ms": row.get("deadline_overrun_ms"),
        "solve_censored": row.get("solve_censored"),
        "feasible_before_deadline": row.get("feasible_before_deadline"),
        "returned_before_deadline": row.get("returned_before_deadline"),
        "incumbent_ms": row.get("incumbent_ms"),
        "source_solver": row.get("source_solver"),
        "selector_ms": row.get("selector_ms"),
        "set_member_count": row.get("set_member_count"),
    }
    policy = "strict_max_vehicles" if row.get("exact_vehicle_count") is not None and row.get("lane") == "exact-k" else row.get("policy", "free_fleet_min_k_lb")
    scored = _baselines_score(synthetic_inst, res_like, policy=policy, budget_ms=budget_ms)
    if mode == "strict_returned_before_deadline":
        if not scored["completed_returned_before_deadline"]:
            scored["completed"] = False
            scored["scored_objective"] = 2.0 * float(row["reference_objective"])
    elif mode != "anytime_feasible_before_deadline":
        raise ValueError(f"unknown_a1_mode:{mode}")
    return {"algorithm_id": row["algorithm_id"], **scored}


def run_a1_baselines_clean_audit(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    smoke: bool = False,
) -> dict[str, Any]:
    """Audit all 6 dual_timing files from baselines_2026 under anytime & strict return modes."""
    base_dir = _REPO / "experiments" / "baselines_2026"
    files = sorted(base_dir.glob("dual_timing_s*_b*.json"))
    n_boot = 200 if smoke else 10000

    uncensored_anomalies: list[dict[str, Any]] = []
    censored_callback_breakdown: Counter[tuple[float, int, str, str]] = Counter()
    cleaned_runs: dict[str, Any] = {}

    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        seed = int(doc["seed"])
        budget_ms = float(doc["budget_ms"])
        run_key = f"s{seed}_b{int(budget_ms)}"
        modes_out: dict[str, Any] = {}

        # Scan raw rows once for anomaly enumeration
        for suite_id, sdata in doc["suites"].items():
            for lane in ("free_fleet", "exact-k"):
                policy = "free_fleet_min_k_lb" if lane == "free_fleet" else "strict_max_vehicles"
                for row in sdata[lane]["rows"]:
                    overrun = float(row.get("deadline_overrun_ms") or 0.0)
                    if row.get("completed") and overrun > 0.0:
                        if row.get("solve_censored"):
                            censored_callback_breakdown[(budget_ms, seed, suite_id, lane)] += 1
                        else:
                            re_any = reevaluate_baselines_row(
                                {**row, "policy": policy, "lane": lane},
                                budget_ms=budget_ms,
                                mode="anytime_feasible_before_deadline",
                            )
                            uncensored_anomalies.append({
                                "file": path.name,
                                "seed": seed,
                                "budget_ms": budget_ms,
                                "suite_id": suite_id,
                                "lane": lane,
                                "algorithm_id": row["algorithm_id"],
                                "instance_id": row["instance_id"],
                                "solve_ms": row.get("solve_ms"),
                                "deadline_overrun_ms": row.get("deadline_overrun_ms"),
                                "solve_censored": row.get("solve_censored"),
                                "feasible_before_deadline": row.get("feasible_before_deadline"),
                                "old_completed": row.get("completed"),
                                "old_scored_objective": row.get("scored_objective"),
                                "clean_completed": re_any["completed"],
                                "clean_scored_objective": re_any["scored_objective"],
                                "reference_objective": row["reference_objective"],
                            })

        for mode in ("anytime_feasible_before_deadline", "strict_returned_before_deadline"):
            suites_out: dict[str, Any] = {}
            pooled_rows: dict[str, dict[str, list[dict[str, Any]]]] = {"free_fleet": {}, "exact-k": {}}
            true_or_rows: dict[str, list[dict[str, Any]]] = {}

            for suite_id in EXTERNAL_SUITES:
                sdata = doc["suites"][suite_id]
                lanes_out: dict[str, Any] = {}
                for lane in ("free_fleet", "exact-k"):
                    policy = "free_fleet_min_k_lb" if lane == "free_fleet" else "strict_max_vehicles"
                    by_alg: dict[str, list[dict[str, Any]]] = {}
                    for raw_row in sdata[lane]["rows"]:
                        cleaned = reevaluate_baselines_row(
                            {**raw_row, "policy": policy, "lane": lane},
                            budget_ms=budget_ms,
                            mode=mode,
                        )
                        aid = cleaned["algorithm_id"]
                        by_alg.setdefault(aid, []).append(cleaned)
                        pooled_rows[lane].setdefault(aid, []).append(cleaned)
                        if lane == "exact-k" and suite_id in TRUE_OR_SUITES:
                            true_or_rows.setdefault(aid, []).append(cleaned)

                    contrasts = {}
                    for aid, arows in by_alg.items():
                        for base_id in ("SBS", "VBS"):
                            if base_id in by_alg and aid != base_id and not (aid == "SBS" and base_id == "VBS"):
                                contrasts[f"{aid}_vs_{base_id}"] = _paired_contrast(
                                    arows, by_alg[base_id], seed=seed, bootstrap_samples=n_boot
                                )
                    _apply_holm_to_contrasts(contrasts, section="overall")
                    _apply_holm_to_contrasts(contrasts, section="common_completed")
                    lanes_out[lane] = {
                        "overall": {aid: _baselines_summary(rows) for aid, rows in by_alg.items()},
                        "comparisons": contrasts,
                    }
                suites_out[suite_id] = lanes_out

            agg_out: dict[str, Any] = {}
            for tag, bucket in (
                ("pooled_430_free_fleet", pooled_rows["free_fleet"]),
                ("pooled_430_exact_k", pooled_rows["exact-k"]),
                ("true_or_174_exact_k", true_or_rows),
            ):
                contrasts = {}
                for aid, arows in bucket.items():
                    for base_id in ("SBS", "VBS"):
                        if base_id in bucket and aid != base_id and not (aid == "SBS" and base_id == "VBS"):
                            contrasts[f"{aid}_vs_{base_id}"] = _paired_contrast(
                                arows, bucket[base_id], seed=seed, bootstrap_samples=n_boot
                            )
                _apply_holm_to_contrasts(contrasts, section="overall")
                _apply_holm_to_contrasts(contrasts, section="common_completed")
                agg_out[tag] = {
                    "overall": {aid: _baselines_summary(rows) for aid, rows in bucket.items()},
                    "comparisons": contrasts,
                }

            modes_out[mode] = {"suites": suites_out, "aggregates": agg_out}
        cleaned_runs[run_key] = {"seed": seed, "budget_ms": budget_ms, "modes": modes_out}

    report = {
        "schema_version": "m6-wave1-a1-baselines-clean-audit/v1",
        "generated_at": _utc_now(),
        "source_files": [p.name for p in files],
        "uncensored_overrun_anomalies_count": len(uncensored_anomalies),
        "uncensored_overrun_anomalies": uncensored_anomalies,
        "censored_callback_overrun_total": sum(censored_callback_breakdown.values()),
        "censored_callback_by_budget_seed_suite_lane": [
            {"budget_ms": k[0], "seed": k[1], "suite_id": k[2], "lane": k[3], "count": v}
            for k, v in sorted(censored_callback_breakdown.items())
        ],
        "runs": cleaned_runs,
    }
    _write_clean_json(out_dir / "a1_baselines_2026_clean_audit.json", report)
    return report


# =============================================================================
# Part A2: M2 & M3 strict completed_before_deadline audit
# =============================================================================


def _summarize_m_records(records: Sequence[Mapping[str, Any]], *, strict: bool, budget_ms: float) -> dict[str, Any]:
    n = len(records)
    comp_flags = [
        is_strict_completed_before_deadline(r, budget_ms=budget_ms)
        if strict
        else (r.get("status") == "ok" and r.get("tour_length") is not None)
        for r in records
    ]
    comp_rows = [r for r, flag in zip(records, comp_flags, strict=True) if flag]
    refs = [float(r["reference_objective"]) for r in records]
    penalized_vals = [
        float(r["tour_length"]) if flag else 2.0 * float(r["reference_objective"])
        for r, flag in zip(records, comp_flags, strict=True)
    ]
    bex_cnt = sum(1 for r in records if r.get("budget_exhausted") is True)
    ok_bex_cnt = sum(
        1 for r in records if r.get("status") == "ok" and r.get("tour_length") is not None and r.get("budget_exhausted") is True
    )
    return {
        "n_instances": n,
        "completed_count": len(comp_rows),
        "completion_rate": round(len(comp_rows) / n, 6) if n else 0.0,
        "ok_budget_exhausted_count": ok_bex_cnt,
        "budget_exhausted_count": bex_cnt,
        "mean_completed_tour_length": round(statistics.mean(float(r["tour_length"]) for r in comp_rows), 4) if comp_rows else None,
        "mean_penalized_objective": round(statistics.mean(penalized_vals), 4) if penalized_vals else None,
        "penalized_gap_pct": round(100.0 * (sum(penalized_vals) / sum(refs) - 1.0), 4) if refs else None,
        "completed_gap_pct": round(
            100.0 * (sum(float(r["tour_length"]) for r in comp_rows) / sum(float(r["reference_objective"]) for r in comp_rows) - 1.0), 4
        ) if comp_rows else None,
    }


def _to_contrast_rows(records: Sequence[Mapping[str, Any]], *, strict: bool, budget_ms: float) -> list[dict[str, Any]]:
    by_id = sorted(records, key=lambda r: str(r["instance_id"]))
    out = []
    for r in by_id:
        comp = (
            is_strict_completed_before_deadline(r, budget_ms=budget_ms)
            if strict
            else (r.get("status") == "ok" and r.get("tour_length") is not None)
        )
        ref = float(r["reference_objective"])
        obj = float(r["tour_length"]) if comp and r.get("tour_length") is not None else 2.0 * ref
        out.append({
            "instance_id": r["instance_id"],
            "completed": comp,
            "scored_objective": obj,
            "reference_objective": ref,
        })
    return out


def _compare_record_family(
    records_by_alg: Mapping[str, Sequence[Mapping[str, Any]]],
    comparisons: Sequence[tuple[str, str, str]],
    *,
    budget_ms: float,
    seed: int,
    n_boot: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mode_name, strict in (("legacy_ok_including_exhausted", False), ("strict_completed_before_deadline", True)):
        family_res: dict[str, Any] = {}
        for label, cand_id, base_id in comparisons:
            cand_rows = _to_contrast_rows(records_by_alg[cand_id], strict=strict, budget_ms=budget_ms)
            base_rows = _to_contrast_rows(records_by_alg[base_id], strict=strict, budget_ms=budget_ms)
            c = _paired_contrast(cand_rows, base_rows, seed=seed, bootstrap_samples=n_boot)
            c["candidate_id"] = cand_id
            c["baseline_id"] = base_id
            family_res[label] = c
        _apply_holm_to_contrasts(family_res, section="overall")
        _apply_holm_to_contrasts(family_res, section="common_completed")
        out[mode_name] = family_res
    return out


def run_a2_m2_m3_strict_deadline_audit(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    smoke: bool = False,
) -> dict[str, Any]:
    """Audit M3 (500ms & 25ms) and M2 (500ms & 25ms) blind suites under strict deadline semantics."""
    n_boot = 200 if smoke else 10000

    # 1. M3 blind_120 (direct from publication_input.json, zero blind file load needed)
    m3_pub = json.loads((_REPO / "experiments/milestone3/phase3d_blind_eval/publication_input.json").read_text(encoding="utf-8"))
    m3_out: dict[str, Any] = {}
    comp_500_specs: list[tuple[str, str, str]] = []
    for seed in PHASE3C_SEEDS:
        m30 = f"m3_3c_standard_500ms_arm_m3_0_pure_eoh_s{seed}"
        m31 = f"m3_3c_standard_500ms_arm_m3_1_plain_text_s{seed}"
        m32 = f"m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s{seed}"
        m33 = f"m3_3c_standard_500ms_arm_m3_3_full_dynamic_s{seed}"
        comp_500_specs.extend([
            (f"s{seed}__m3_3_vs_m3_0", m33, m30),
            (f"s{seed}__m3_3_vs_m3_1", m33, m31),
            (f"s{seed}__m3_3_vs_m3_2", m33, m32),
            (f"s{seed}__m3_2_vs_m3_1", m32, m31),
            (f"s{seed}__m3_2_vs_m3_0", m32, m30),
            (f"s{seed}__m3_3_vs_c1_tworegime", m33, "i605_cvrp_c1_tworegime"),
            (f"s{seed}__m3_3_vs_cw_parallel_merge", m33, "cw_parallel_merge"),
            (f"s{seed}__m3_3_vs_cw_relocate_2opt", m33, "cw_relocate_2opt"),
        ])
    comp_500_specs.extend([
        ("backbone__r2_l3_evolved_vs_l3_ctrl_500ms", M3_EXTRA_L3_SOLVER_ID, "m3_l3_ctrl_500ms"),
        ("backbone__m3_3_s20261125_vs_l3_ctrl_500ms", "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125", "m3_l3_ctrl_500ms"),
        ("backbone__m3_3_s20261125_vs_m2_champ_s20261123", "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"),
    ])
    comp_25_specs: list[tuple[str, str, str]] = []
    for seed in PHASE3C_SEEDS:
        m30 = f"m3_3c_tight_25ms_arm_m3_0_pure_eoh_s{seed}"
        m31 = f"m3_3c_tight_25ms_arm_m3_1_plain_text_s{seed}"
        m32 = f"m3_3c_tight_25ms_arm_m3_2_fixed_l2a_s{seed}"
        m33 = f"m3_3c_tight_25ms_arm_m3_3_full_dynamic_s{seed}"
        comp_25_specs.extend([
            (f"s{seed}__m3_3_25_vs_m3_0_25", m33, m30),
            (f"s{seed}__m3_3_25_vs_m3_1_25", m33, m31),
            (f"s{seed}__m3_3_25_vs_m3_2_25", m33, m32),
            (f"s{seed}__m3_2_25_vs_m3_1_25", m32, m31),
            (f"s{seed}__m3_3_25_vs_l3_ctrl_25", m33, "m3_l3_ctrl_25ms"),
            (f"s{seed}__m3_2_25_vs_l3_ctrl_25", m32, "m3_l3_ctrl_25ms"),
            (f"s{seed}__m3_3_25_vs_c1_tworegime", m33, "i605_cvrp_c1_tworegime"),
        ])

    for label, key, bms, specs in (
        ("standard_500ms", "records_500ms", 500.0, comp_500_specs),
        ("tight_25ms", "records_25ms", 25.0, comp_25_specs),
    ):
        recs = m3_pub[key]["cvrp_m3_blind_120"]
        by_alg: dict[str, list[Mapping[str, Any]]] = {}
        for r in recs:
            by_alg.setdefault(r["algorithm_id"], []).append(r)
        strict_common_ids = set.intersection(*[
            {r["instance_id"] for r in rows if is_strict_completed_before_deadline(r, budget_ms=bms)}
            for rows in by_alg.values()
        ])
        legacy_common_ids = set.intersection(*[
            {r["instance_id"] for r in rows if r.get("status") == "ok" and r.get("tour_length") is not None}
            for rows in by_alg.values()
        ])
        m3_out[label] = {
            "budget_ms": bms,
            "legacy_common_completed_count": len(legacy_common_ids),
            "strict_common_completed_count": len(strict_common_ids),
            "algorithms": {
                aid: {
                    "legacy_ok": _summarize_m_records(rows, strict=False, budget_ms=bms),
                    "strict_completed_before_deadline": _summarize_m_records(rows, strict=True, budget_ms=bms),
                }
                for aid, rows in sorted(by_alg.items())
            },
            "hypothesis_tests": _compare_record_family(
                by_alg, specs, budget_ms=bms, seed=20261124, n_boot=n_boot
            ),
        }

    # 2. M2 blind_120: 500ms from release per_instance_records; 25ms re-evaluated strictly in-memory on verified sealed suite
    m2_pir = json.loads(
        (_REPO / "knowledge_store/releases/20261123-main-co-workbench-m2/results/per_instance_records.json").read_text(encoding="utf-8")
    )["records"]
    m2_500_by_alg: dict[str, list[Mapping[str, Any]]] = {}
    m2_ref_by_inst: dict[str, float] = {}
    for r in m2_pir:
        if r.get("suite_id") == "cvrp_m2_blind_120":
            m2_500_by_alg.setdefault(r["algorithm_id"], []).append(r)
            if r.get("reference_objective") is not None:
                m2_ref_by_inst[str(r["instance_id"])] = float(r["reference_objective"])

    from agent_skill_loop.interface_design.blind_eval import STANDARD_ARM_SEED_IDS, load_phase2b_frozen_roster

    m2_frozen = {fs.solver_id: fs for fs in load_phase2b_frozen_roster(_REPO)}
    m2_blind_suite, m2_ver = unseal_and_verify_m2_blind_suite(
        sealed_path=_REPO / ".secrets" / "m2_blind" / "cvrp_m2_blind_120_sealed.json",
        commitment_path=BLIND_COMMITMENT_PATH,
    )
    m2_25_ids = ["s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge", *TIGHT_SOLVER_IDS]
    m2_25_by_alg: dict[str, list[dict[str, Any]]] = {aid: [] for aid in m2_25_ids}
    for inst in m2_blind_suite["instances"]:
        iid = str(inst["instance_id"])
        ref = float(inst.get("reference_objective") or m2_ref_by_inst[iid])
        for aid in m2_25_ids:
            if aid in m2_frozen:
                res = evaluate_frozen_interface_solver(
                    m2_frozen[aid], inst, distance_convention="euc_2d_float",
                    vehicle_limit_policy="unconstrained", solve_deadline_ms=25.0, enforce_wall_deadline=True,
                )
            else:
                res = evaluate_algorithm_on_instance(
                    aid, inst, distance_convention="euc_2d_float",
                    vehicle_limit_policy="unconstrained", time_budget_ms=25.0,
                    record_trace=False, enforce_wall_deadline=True,
                )
            m2_25_by_alg[aid].append({
                "instance_id": iid,
                "status": res["status"],
                "valid": res["valid"],
                "tour_length": res["tour_length"],
                "reference_objective": ref,
                "solve_ms": res["solve_ms"],
                "budget_ms": 25.0,
                "budget_exhausted": bool(res.get("budget_exhausted", False)),
                "time_limit_reached": bool(res.get("time_limit_reached", False)),
                "solve_censored": bool(res.get("solve_censored", False)),
            })

    # Synthetic paired-seed averages on M2 500ms for exact match with M2 protocol
    def _seed_avg_rows(arm: str) -> list[dict[str, Any]]:
        s1, s2 = STANDARD_ARM_SEED_IDS[arm]
        r1 = sorted(m2_500_by_alg[s1], key=lambda x: str(x["instance_id"]))
        r2 = sorted(m2_500_by_alg[s2], key=lambda x: str(x["instance_id"]))
        out_r = []
        for a, b in zip(r1, r2, strict=True):
            assert a["instance_id"] == b["instance_id"]
            c1 = is_strict_completed_before_deadline(a, budget_ms=500.0)
            c2 = is_strict_completed_before_deadline(b, budget_ms=500.0)
            ref = float(a["reference_objective"])
            t1 = float(a["tour_length"]) if c1 else 2.0 * ref
            t2 = float(b["tour_length"]) if c2 else 2.0 * ref
            out_r.append({
                "instance_id": a["instance_id"],
                "status": "ok" if (c1 and c2) else "timeout",
                "valid": bool(c1 and c2),
                "tour_length": 0.5 * (t1 + t2),
                "reference_objective": ref,
                "solve_ms": max(float(a.get("solve_ms") or 0.0), float(b.get("solve_ms") or 0.0)),
                "budget_ms": 500.0,
                "budget_exhausted": False,
            })
        return out_r

    m2_500_extended = dict(m2_500_by_alg)
    for arm in STANDARD_ARM_SEED_IDS:
        m2_500_extended[f"__arm_avg__{arm}"] = _seed_avg_rows(arm)

    m2_500_specs = [
        ("H1_llm_planner_vs_fixed_pointwise_500ms_paired_avg", "__arm_avg__llm_diagnostic_planner", "__arm_avg__fixed_pointwise"),
        ("H2_llm_planner_s20261123_vs_c1_tworegime_500ms", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123", "i605_cvrp_c1_tworegime"),
        ("H2b_llm_planner_s20261123_vs_r5_spiral_500ms", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123", "s2_r5_spiral"),
        ("H3_llm_planner_vs_rule_planner_500ms_paired_avg", "__arm_avg__llm_diagnostic_planner", "__arm_avg__diagnostic_rule_planner"),
        ("H3b_llm_planner_s20261123_vs_bare_cw_500ms", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123", "cw_parallel_merge"),
        ("H5b_l2b_ctrl_vs_bare_cw_at_500ms", "m2_2b_l2b_ctrl_static_refresh", "cw_parallel_merge"),
    ]
    m2_25_specs = [
        ("H4a_protocol_t1_rule_25ms_vs_t2_rule_500ms_at_25ms", "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122", "m2_2b_standard_500ms_diagnostic_rule_planner_s20261122"),
        ("H4b_protocol_t1_llm_25ms_vs_t2_rule_500ms_at_25ms", "m2_2b_tight_25ms_llm_diagnostic_planner_s20261122", "m2_2b_standard_500ms_diagnostic_rule_planner_s20261122"),
        ("H4c_protocol_t1_rule_25ms_vs_bare_cw_at_25ms", "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122", "cw_parallel_merge"),
        ("H5a_l2a_evolved_vs_l2b_ctrl_at_25ms", "m2_2b_l2a_evolved_s20261122", "m2_2b_l2b_ctrl_static_refresh"),
    ]
    m2_25_strict_common = set.intersection(*[
        {r["instance_id"] for r in rows if is_strict_completed_before_deadline(r, budget_ms=25.0)}
        for rows in m2_25_by_alg.values()
    ])
    m2_25_legacy_common = set.intersection(*[
        {r["instance_id"] for r in rows if r.get("status") == "ok" and r.get("tour_length") is not None}
        for rows in m2_25_by_alg.values()
    ])

    report = {
        "schema_version": "m6-wave1-a2-m2-m3-strict-deadline-audit/v1",
        "generated_at": _utc_now(),
        "m2_blind_verification": m2_ver,
        "m3": m3_out,
        "m2": {
            "standard_500ms": {
                "budget_ms": 500.0,
                "algorithms": {
                    aid: {
                        "legacy_ok": _summarize_m_records(rows, strict=False, budget_ms=500.0),
                        "strict_completed_before_deadline": _summarize_m_records(rows, strict=True, budget_ms=500.0),
                    }
                    for aid, rows in sorted(m2_500_by_alg.items())
                },
                "hypothesis_tests": _compare_record_family(
                    m2_500_extended, m2_500_specs, budget_ms=500.0, seed=20261123, n_boot=n_boot
                ),
            },
            "tight_25ms": {
                "budget_ms": 25.0,
                "legacy_common_completed_count": len(m2_25_legacy_common),
                "strict_common_completed_count": len(m2_25_strict_common),
                "algorithms": {
                    aid: {
                        "legacy_ok": _summarize_m_records(rows, strict=False, budget_ms=25.0),
                        "strict_completed_before_deadline": _summarize_m_records(rows, strict=True, budget_ms=25.0),
                    }
                    for aid, rows in sorted(m2_25_by_alg.items())
                },
                "hypothesis_tests": _compare_record_family(
                    m2_25_by_alg, m2_25_specs, budget_ms=25.0, seed=20261123, n_boot=n_boot
                ),
            },
        },
    }
    _write_clean_json(out_dir / "a2_m2_m3_strict_deadline_audit.json", report)
    return report


# =============================================================================
# Shared single-worker suite evaluation & caching for A3 and A4
# =============================================================================


def _prepare_external_suites() -> dict[str, dict[str, Any]]:
    prepared: dict[str, dict[str, Any]] = {}
    for sid in EXTERNAL_SUITES:
        suite = load_profile_suite(BENCHMARK_ID, sid, split="heldout")
        dist = str(suite["distance_convention"])
        insts = []
        for inst in suite["instances"]:
            row = dict(inst)
            if row.get("k_vehicles") is None and row.get("max_vehicles") is None:
                nn = evaluate_algorithm_on_instance(
                    "nn", row, distance_convention=dist,
                    vehicle_limit_policy="unconstrained", enforce_wall_deadline=False, record_trace=False,
                )
                row["k_vehicles"] = int(nn["route_count"])
                row["exact_k_target_source"] = "nn_route_count"
            else:
                row["exact_k_target_source"] = "manifest_k_vehicles"
            insts.append(row)
        prepared[sid] = {"suite_id": sid, "distance_convention": dist, "instances": insts}
    return prepared


def _eval_single_worker_cached(
    *,
    solver_id: str,
    kind: str,
    payload: Any,
    suite_id: str,
    suite_data: Mapping[str, Any],
    budget_ms: float,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    """Evaluate one solver on one suite under strict single-worker execution with leak-safe cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{solver_id}__{suite_id}__{int(budget_ms)}.json"
    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    dist = str(suite_data["distance_convention"])
    policy = "unconstrained" if suite_id == "cvrp_m32_blind_120" else "free_fleet_min_k_lb"
    solver_obj = payload if kind == "catalog" else FrozenInterfaceSolver.from_dict(payload)
    rows: list[dict[str, Any]] = []

    for inst in suite_data["instances"]:
        if kind == "catalog":
            res = evaluate_algorithm_on_instance(
                solver_obj, inst, distance_convention=dist,
                vehicle_limit_policy=policy, time_budget_ms=budget_ms,
                record_trace=False, enforce_wall_deadline=True,
            )
        else:
            res = evaluate_frozen_interface_solver(
                solver_obj, inst, distance_convention=dist,
                vehicle_limit_policy=policy, solve_deadline_ms=budget_ms,
                enforce_wall_deadline=True,
            )

        ref = float(inst["reference_objective"])
        obj_raw = res.get("tour_length", res.get("objective"))
        obj = float(obj_raw) if isinstance(obj_raw, (int, float)) and math.isfinite(obj_raw) and obj_raw > 0 else None
        valid = res.get("valid") is True and obj is not None
        rc = res.get("route_count")
        tv = inst.get("k_vehicles", res.get("target_vehicles"))
        exact = (int(rc) == int(tv)) if (valid and rc is not None and tv is not None) else res.get("exact_vehicle_count")
        timing = dual_timing_fields(res, budget_ms=budget_ms, feasible=valid)
        uncensored_overrun = (
            (not timing["solve_censored"])
            and (timing["deadline_overrun_ms"] is not None)
            and (timing["deadline_overrun_ms"] > 0.0)
        )
        default_comp = res.get("status") == "ok" and not res.get("budget_exhausted", False)
        completed = valid and res.get("completed", default_comp) is True and not uncensored_overrun

        rows.append({
            "instance_id": str(inst["instance_id"]),
            "size": int(inst.get("size", len(inst["demands"]))),
            "cvrplib_set": inst.get("cvrplib_set"),
            "reference_objective": ref,
            "objective": obj if valid else None,
            "tour_length": obj if valid else None,
            "tour_length_euc_2d_float": res.get("tour_length_euc_2d_float"),
            "valid": valid,
            "completed": completed,
            "scored_objective": obj if completed else 2.0 * ref,
            "rel_gap": ((obj - ref) / ref) if (completed and obj is not None) else None,
            "route_count": rc,
            "target_vehicles": tv,
            "exact_vehicle_count": exact,
            "status": res.get("status"),
            "budget_exhausted": bool(res.get("budget_exhausted", False)),
            "uncensored_deadline_overrun": uncensored_overrun,
            **timing,
        })

    _write_clean_json(cache_file, {"solver_id": solver_id, "suite_id": suite_id, "budget_ms": budget_ms, "rows": rows})
    return rows


def _load_rows_list(cache_or_rows: Any) -> list[dict[str, Any]]:
    if isinstance(cache_or_rows, dict) and "rows" in cache_or_rows:
        return cache_or_rows["rows"]
    return cache_or_rows


def _project_lane_rows(rows: Sequence[Mapping[str, Any]], *, lane: str) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        ref = float(r["reference_objective"])
        comp = bool(r["completed"]) if lane == "free_fleet" else bool(r["completed"] and r.get("exact_vehicle_count") is True)
        obj = r.get("objective")
        out.append({
            "instance_id": r["instance_id"],
            "size": r["size"],
            "reference_objective": ref,
            "objective": obj,
            "completed": comp,
            "scored_objective": float(obj) if (comp and obj is not None) else 2.0 * ref,
            "exact_vehicle_count": r.get("exact_vehicle_count"),
            "solve_ms": r.get("solve_ms"),
            "budget_ms": r.get("budget_ms"),
            "solve_censored": r.get("solve_censored"),
            "feasible_before_deadline": r.get("feasible_before_deadline"),
            "returned_before_deadline": r.get("returned_before_deadline"),
        })
    return out


def _summarize_lane_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    comp = [r for r in rows if r["completed"]]
    refs = sum(float(r["reference_objective"]) for r in rows)
    scored = sum(float(r["scored_objective"]) for r in rows)
    comp_refs = sum(float(r["reference_objective"]) for r in comp)
    comp_obj = sum(float(r["objective"]) for r in comp)
    timing = summarize_solve_timing(rows)
    solve_vals = [float(r["solve_ms"]) for r in rows if r.get("solve_ms") is not None]
    return {
        "n_instances": n,
        "completed_count": len(comp),
        "completion_rate": round(len(comp) / n, 6) if n else 0.0,
        "ok_mean_tour_length": round(comp_obj / len(comp), 4) if comp else None,
        "ok_gap_pct": round(100.0 * (comp_obj / comp_refs - 1.0), 4) if comp_refs else None,
        "penalized_mean_objective": round(scored / n, 4) if n else None,
        "penalized_gap_pct": round(100.0 * (scored / refs - 1.0), 4) if refs else None,
        "solve_ms_p50": timing["solve_ms_p50"],
        "solve_ms_p95": timing["solve_ms_p95"],
        "solve_ms_max": round(max(solve_vals), 4) if solve_vals else None,
        "censored_count": timing["solve_ms_censored_count"],
    }


def _eval_cached(
    *,
    solver_id: str,
    kind: str,
    payload: Any,
    suite_id: str,
    suite_data: Mapping[str, Any],
    budget_ms: float,
    cache_dir: Path,
) -> list[dict[str, Any]]:
    raw = _eval_single_worker_cached(
        solver_id=solver_id,
        kind=kind,
        payload=payload,
        suite_id=suite_id,
        suite_data=suite_data,
        budget_ms=budget_ms,
        cache_dir=cache_dir,
    )
    return _load_rows_list(raw)


# =============================================================================
# Part A3: M3.2 2x2 orthogonal budget attribution (train_timeout x eval_timeout)
# =============================================================================


def run_a3_m32_2x2_orthogonal(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    smoke: bool = False,
) -> dict[str, Any]:
    """Run clean single-worker 2x2 train_timeout x eval_timeout orthogonal evaluation on M3.2 solvers."""
    cache_dir = out_dir / "cache_nocontention"
    n_boot = 200 if smoke else 10000

    sealed_m32, _, ver32 = read_verified_milestone_blind_payload(
        sealed_path=Path(r"C:\Users\24294\.agent_skill_custody_m32\cvrp_m32_blind_120_sealed.json"),
        commitment_path=M32_BLIND_COMMITMENT_PATH,
    )
    blind_suite = {
        "suite_id": "cvrp_m32_blind_120",
        "distance_convention": sealed_m32["distance_convention"],
        "instances": sealed_m32["instances"],
    }
    ext_suites = _prepare_external_suites()
    all_suites = {"cvrp_m32_blind_120": blind_suite, **ext_suites}
    if smoke:
        all_suites = {
            k: {**v, "instances": v["instances"][:4]}
            for k, v in all_suites.items()
        }

    # Solver specs
    m32_snap_dir = _REPO / "experiments" / "milestone3_2" / "roster_snapshots"
    specs: list[tuple[str, str, Any]] = [("cw_relocate_2opt", "catalog", "cw_relocate_2opt")]
    for seed in M32_SEEDS:
        for tag, fname in (
            (f"m32_ckpt36_s{seed}", f"{seed}_checkpoint_36.json"),
            (f"m32_ckpt400_s{seed}", f"{seed}_checkpoint_400.json"),
            (f"m32_timeout_2000ms_s{seed}_raw", f"{seed}_control_timeout_2000ms.json"),
        ):
            raw = json.loads((m32_snap_dir / fname).read_text(encoding="utf-8"))
            specs.append((tag, "frozen", raw.get("frozen_solver") or raw))

    raw_rows: dict[float, dict[str, dict[str, list[dict[str, Any]]]]] = {500.0: {}, 2000.0: {}}
    for bms in (500.0, 2000.0):
        print(f"[A3] Running eval_timeout={int(bms)}ms across {len(specs)} solvers x {len(all_suites)} suites...", flush=True)
        for sid, kind, payload in specs:
            raw_rows[bms][sid] = {}
            for suite_id, sdata in all_suites.items():
                raw_rows[bms][sid][suite_id] = _eval_cached(
                    solver_id=sid, kind=kind, payload=payload,
                    suite_id=suite_id, suite_data=sdata, budget_ms=bms, cache_dir=cache_dir,
                )

    # Summarize blind_120 & external 430 / 174
    suite_tables: dict[str, Any] = {}
    for bms in (500.0, 2000.0):
        b_tag = f"{int(bms)}ms"
        suite_tables[b_tag] = {}
        for sid, _, _ in specs:
            blind_ff = _project_lane_rows(raw_rows[bms][sid]["cvrp_m32_blind_120"], lane="free_fleet")
            ext430_raw = [r for ext_id in EXTERNAL_SUITES for r in raw_rows[bms][sid][ext_id]]
            or174_raw = [r for ext_id in TRUE_OR_SUITES for r in raw_rows[bms][sid][ext_id]]
            suite_tables[b_tag][sid] = {
                "m32_blind_120_free_fleet": _summarize_lane_rows(blind_ff),
                "ext430_free_fleet": _summarize_lane_rows(_project_lane_rows(ext430_raw, lane="free_fleet")),
                "ext430_exact_k": _summarize_lane_rows(_project_lane_rows(ext430_raw, lane="exact-k")),
                "true_or_174_exact_k": _summarize_lane_rows(_project_lane_rows(or174_raw, lane="exact-k")),
                "by_suite_free_fleet": {
                    ext_id: _summarize_lane_rows(_project_lane_rows(raw_rows[bms][sid][ext_id], lane="free_fleet"))
                    for ext_id in EXTERNAL_SUITES
                },
            }

    # Compute 2x2 orthogonal contrasts on blind_120 & ext430_free_fleet & true_or_174_exact_k
    orthogonal_contrasts: dict[str, Any] = {}
    for domain_label, suite_list, lane in (
        ("m32_blind_120_free_fleet", ("cvrp_m32_blind_120",), "free_fleet"),
        ("ext430_free_fleet", EXTERNAL_SUITES, "free_fleet"),
        ("true_or_174_exact_k", TRUE_OR_SUITES, "exact-k"),
    ):
        domain_contrasts: dict[str, Any] = {}
        for seed in M32_SEEDS:
            c400 = f"m32_ckpt400_s{seed}"
            t2k = f"m32_timeout_2000ms_s{seed}_raw"

            def _get(sid: str, bms: float) -> list[dict[str, Any]]:
                combined = [r for s in suite_list for r in raw_rows[bms][sid][s]]
                return _project_lane_rows(combined, lane=lane)

            # 1. Pure search-budget effect at fixed eval=500ms: train2000@500 vs train500@500
            domain_contrasts[f"s{seed}__search_effect_at_eval500ms"] = {
                **_paired_contrast(_get(t2k, 500.0), _get(c400, 500.0), seed=seed, bootstrap_samples=n_boot),
                "candidate_label": f"{t2k}@500ms",
                "baseline_label": f"{c400}@500ms",
            }
            # 2. Pure search-budget effect at fixed eval=2000ms: train2000@2000 vs train500@2000
            domain_contrasts[f"s{seed}__search_effect_at_eval2000ms"] = {
                **_paired_contrast(_get(t2k, 2000.0), _get(c400, 2000.0), seed=seed, bootstrap_samples=n_boot),
                "candidate_label": f"{t2k}@2000ms",
                "baseline_label": f"{c400}@2000ms",
            }
            # 3. Pure eval-deadline effect for train500ms: train500@2000 vs train500@500
            domain_contrasts[f"s{seed}__eval_deadline_effect_train500ms"] = {
                **_paired_contrast(_get(c400, 2000.0), _get(c400, 500.0), seed=seed, bootstrap_samples=n_boot),
                "candidate_label": f"{c400}@2000ms",
                "baseline_label": f"{c400}@500ms",
            }
            # 4. Pure eval-deadline effect for train2000ms: train2000@2000 vs train2000@500
            domain_contrasts[f"s{seed}__eval_deadline_effect_train2000ms"] = {
                **_paired_contrast(_get(t2k, 2000.0), _get(t2k, 500.0), seed=seed, bootstrap_samples=n_boot),
                "candidate_label": f"{t2k}@2000ms",
                "baseline_label": f"{t2k}@500ms",
            }
            # 5. Confounded diagonal (old comparison): train2000@2000 vs train500@500
            domain_contrasts[f"s{seed}__confounded_diagonal_t2k@2k_vs_c400@500"] = {
                **_paired_contrast(_get(t2k, 2000.0), _get(c400, 500.0), seed=seed, bootstrap_samples=n_boot),
                "candidate_label": f"{t2k}@2000ms",
                "baseline_label": f"{c400}@500ms",
            }
        _apply_holm_to_contrasts(domain_contrasts, section="overall")
        _apply_holm_to_contrasts(domain_contrasts, section="common_completed")
        orthogonal_contrasts[domain_label] = domain_contrasts

    report = {
        "schema_version": "m6-wave1-a3-m32-2x2-orthogonal/v1",
        "generated_at": _utc_now(),
        "smoke": smoke,
        "m32_blind_verification": ver32,
        "suite_tables": suite_tables,
        "orthogonal_contrasts": orthogonal_contrasts,
    }
    _write_clean_json(out_dir / "a3_m32_2x2_budget_orthogonal.json", report)
    return report


# =============================================================================
# Part A4: Single-worker no-contention 430-instance benchmark + concurrency diff
# =============================================================================


def _build_a4_representative_specs() -> list[tuple[str, str, str, Any]]:
    specs: list[tuple[str, str, str, Any]] = [
        ("nn", "01_classical", "catalog", "nn"),
        ("cw_parallel_merge", "01_classical", "catalog", "cw_parallel_merge"),
        ("cw_2opt", "01_classical", "catalog", "cw_2opt"),
        ("cw_relocate_2opt", "01_classical", "catalog", "cw_relocate_2opt"),
        ("eohs_cvrp_f1", "02_upstream", "catalog", "eohs_cvrp_f1"),
        ("eoh_cvrp_f1", "02_upstream", "catalog", "eoh_cvrp_f1"),
        ("s2_r5_spiral", "03_m1_i605", "catalog", "s2_r5_spiral"),
        ("i605_cvrp_c1_tworegime", "03_m1_i605", "catalog", "i605_cvrp_c1_tworegime"),
    ]
    from agent_skill_loop.interface_design.blind_eval import load_phase2b_frozen_roster
    from agent_skill_loop.interface_design.blind_eval_m3 import load_phase3c_frozen_roster

    m2_by_id = {s.solver_id: s for s in load_phase2b_frozen_roster(_REPO)}
    specs.append((
        "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
        "04_m2",
        "frozen",
        m2_by_id["m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"].to_dict(),
    ))

    m3_by_id = {s.solver_id: s for s in load_phase3c_frozen_roster(_REPO)}
    for sid in (
        "m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126",
        "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125",
    ):
        specs.append((sid, "05_m3", "frozen", m3_by_id[sid].to_dict()))

    snaps = [
        ("m32_ckpt36_s20261125", "06_m32", "experiments/milestone3_2/roster_snapshots/20261125_checkpoint_36.json"),
        ("m32_ckpt400_s20261125", "06_m32", "experiments/milestone3_2/roster_snapshots/20261125_checkpoint_400.json"),
        ("m32_timeout_2000ms_s20261124_raw", "06_m32", "experiments/milestone3_2/roster_snapshots/20261124_control_timeout_2000ms.json"),
        ("m32_l3b_dual_hook_s20261125", "06_m32", "experiments/milestone3_2/roster_snapshots/20261125_control_l3b_dual_hook.json"),
        ("m5_ds_legacy_s20261128", "07_m5", "experiments/milestone5_paratera/roster_snapshots/legacy_baseline_500ms_20261128.json"),
        ("m5_ds_whitelist_s20261127", "07_m5", "experiments/milestone5_paratera/roster_snapshots/whitelist_latency_500ms_20261127.json"),
        ("m5_ds_traj_ctrl_s20261128", "07_m5", "experiments/milestone5_paratera/roster_snapshots/trajectory_ctrl_full_500ms_20261128.json"),
        ("m5_qwen_ctrl_s20261125", "07_m5", "experiments/milestone5_paratera/roster_snapshots/model2_ctrl_full_500ms_20261125.json"),
        ("m5_s1_ds_sandbox_s20261128", "08_m5_s1", "experiments/milestone5_s1_sandbox_ablation/roster_snapshots/m5_s1_DeepSeek-V4.1-Flash_arm_s1_2_sandbox_only_s20261128.json"),
        ("m5_s2_ds_11_combined_s20261125", "09_m5_s2", "experiments/milestone5_s2_multiscale/exp2c/roster_snapshots/m5_s2_DeepSeek-V4.1-Flash_arm_s2_11_combined_s20261125.json"),
        ("m5_s2_qwen_11_combined_s20261126", "09_m5_s2", "experiments/milestone5_s2_multiscale/exp2c/roster_snapshots/m5_s2_Qwen4-Max_arm_s2_11_combined_s20261126.json"),
    ]
    for alias, grp, rel in snaps:
        raw = json.loads((_REPO / rel).read_text(encoding="utf-8"))
        specs.append((alias, grp, "frozen", raw.get("frozen_solver") or raw))

    pruned_solver = load_m32_champion_solver(build_pruned_m32_champion(load_raw_m32_champion()))
    specs.append(("m32_timeout_2000ms_s20261124_pruned", "06_m32", "frozen", pruned_solver.to_dict()))
    return specs


def run_a4_430_nocontention(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    a1_report: Mapping[str, Any] | None = None,
    smoke: bool = False,
) -> dict[str, Any]:
    """Run single-worker no-contention 430-instance benchmark across 23 representatives and merge A1 external baselines."""
    cache_dir = out_dir / "cache_nocontention"
    n_boot = 200 if smoke else 10000
    ext_suites = _prepare_external_suites()
    if smoke:
        ext_suites = {k: {**v, "instances": v["instances"][:4]} for k, v in ext_suites.items()}

    specs = _build_a4_representative_specs()
    rows_by_budget: dict[float, dict[str, dict[str, list[dict[str, Any]]]]] = {500.0: {}, 2000.0: {}}
    for bms in (500.0, 2000.0):
        print(f"[A4] Running single-worker eval_timeout={int(bms)}ms across {len(specs)} solvers...", flush=True)
        for idx, (sid, _, kind, payload) in enumerate(specs, 1):
            rows_by_budget[bms][sid] = {}
            for suite_id, sdata in ext_suites.items():
                rows_by_budget[bms][sid][suite_id] = _eval_cached(
                    solver_id=sid, kind=kind, payload=payload,
                    suite_id=suite_id, suite_data=sdata, budget_ms=bms, cache_dir=cache_dir,
                )
            if idx % 5 == 0 or idx == len(specs):
                print(f"[A4]   b={int(bms)}ms progress: {idx}/{len(specs)} solvers done", flush=True)

    # Golden parity check against raw baselines_2026 SBS (s20261124 b500 & b2000)
    golden_parity: dict[str, Any] = {}
    if not smoke:
        for bms, target_sid in ((500.0, "cw_relocate_2opt"), (2000.0, "m32_timeout_2000ms_s20261124_pruned")):
            doc = json.loads((_REPO / f"experiments/baselines_2026/dual_timing_s20261124_b{int(bms)}.json").read_text(encoding="utf-8"))
            diffs = []
            for suite_id in EXTERNAL_SUITES:
                sbs_map = {
                    r["instance_id"]: r
                    for r in doc["suites"][suite_id]["free_fleet"]["rows"]
                    if r["algorithm_id"] == "SBS" and r["completed"]
                }
                for r in rows_by_budget[bms][target_sid][suite_id]:
                    if r["completed"] and r["instance_id"] in sbs_map:
                        diffs.append(abs(float(r["objective"]) - float(sbs_map[r["instance_id"]]["objective"])))
            golden_parity[f"{int(bms)}ms_{target_sid}"] = {
                "common_completed_count": len(diffs),
                "max_abs_diff": float(max(diffs)) if diffs else None,
            }

    # Summarize all 23 representatives + paired tests vs cw_relocate_2opt
    summaries: dict[str, Any] = {}
    for bms in (500.0, 2000.0):
        b_tag = f"{int(bms)}ms"
        tbl: dict[str, Any] = {}
        contrasts_430_ff: dict[str, Any] = {}
        base_430_ff = _project_lane_rows(
            [r for sid in EXTERNAL_SUITES for r in rows_by_budget[bms]["cw_relocate_2opt"][sid]],
            lane="free_fleet",
        )
        for solver_id, stage_group, _, _ in specs:
            r430 = [r for sid in EXTERNAL_SUITES for r in rows_by_budget[bms][solver_id][sid]]
            r174 = [r for sid in TRUE_OR_SUITES for r in rows_by_budget[bms][solver_id][sid]]
            r430_ff = _project_lane_rows(r430, lane="free_fleet")
            r430_ek = _project_lane_rows(r430, lane="exact-k")
            r174_ek = _project_lane_rows(r174, lane="exact-k")
            rx_n500 = _project_lane_rows(
                [r for r in rows_by_budget[bms][solver_id]["cvrp_ext_cvrplib_x_100"] if int(r["size"]) >= 500],
                lane="free_fleet",
            )
            tbl[solver_id] = {
                "stage_group": stage_group,
                "430_free_fleet": _summarize_lane_rows(r430_ff),
                "430_exact_k": _summarize_lane_rows(r430_ek),
                "true_or_174_exact_k": _summarize_lane_rows(r174_ek),
                "set_x_n_ge_500_free_fleet": _summarize_lane_rows(rx_n500),
                "by_suite_free_fleet": {
                    sid: _summarize_lane_rows(_project_lane_rows(rows_by_budget[bms][solver_id][sid], lane="free_fleet"))
                    for sid in EXTERNAL_SUITES
                },
            }
            if solver_id != "cw_relocate_2opt":
                contrasts_430_ff[f"{solver_id}_vs_cw_relocate_2opt"] = _paired_contrast(
                    r430_ff, base_430_ff, seed=20261124, bootstrap_samples=n_boot
                )
        _apply_holm_to_contrasts(contrasts_430_ff, section="overall")
        _apply_holm_to_contrasts(contrasts_430_ff, section="common_completed")
        summaries[b_tag] = {"solvers": tbl, "vs_cw_relocate_2opt_430_free_fleet": contrasts_430_ff}

    # Include A1 cleaned external baselines summary (seed 20261124-20261126 ranges)
    a1_ref = a1_report
    if a1_ref is None:
        a1_path = out_dir / "a1_baselines_2026_clean_audit.json"
        if a1_path.is_file():
            a1_ref = json.loads(a1_path.read_text(encoding="utf-8"))

    external_summary: dict[str, Any] = {}
    if a1_ref is not None:
        for b_tag, b_key in (("500ms", "b500"), ("2000ms", "b2000")):
            external_summary[b_tag] = {}
            for mode in ("anytime_feasible_before_deadline", "strict_returned_before_deadline"):
                mode_out: dict[str, Any] = {}
                for run_key, rdata in a1_ref["runs"].items():
                    if run_key.endswith(b_key):
                        mode_out[run_key] = {
                            "430_free_fleet": rdata["modes"][mode]["aggregates"]["pooled_430_free_fleet"]["overall"],
                            "430_exact_k": rdata["modes"][mode]["aggregates"]["pooled_430_exact_k"]["overall"],
                            "true_or_174_exact_k": rdata["modes"][mode]["aggregates"]["true_or_174_exact_k"]["overall"],
                        }
                external_summary[b_tag][mode] = mode_out

    # Compare M3.2 raw vs pruned Set X >= 500 under no-contention single-worker mode
    m32_jitter_focus = {
        b_tag: {
            sid: {
                "430_free_fleet": summaries[b_tag]["solvers"][sid]["430_free_fleet"],
                "x100_free_fleet": summaries[b_tag]["solvers"][sid]["by_suite_free_fleet"]["cvrp_ext_cvrplib_x_100"],
                "set_x_n_ge_500_free_fleet": summaries[b_tag]["solvers"][sid]["set_x_n_ge_500_free_fleet"],
            }
            for sid in ("m32_timeout_2000ms_s20261124_raw", "m32_timeout_2000ms_s20261124_pruned", "m32_ckpt400_s20261125")
            if sid in summaries[b_tag]["solvers"]
        }
        for b_tag in ("500ms", "2000ms")
    }

    report = {
        "schema_version": "m6-wave1-a4-430-nocontention/v1",
        "generated_at": _utc_now(),
        "smoke": smoke,
        "execution_mode": "strict_single_worker_sequential",
        "golden_parity_vs_baselines_2026_sbs": golden_parity,
        "m32_set_x_nocontention_focus": m32_jitter_focus,
        "summaries": summaries,
        "cleaned_external_baselines_2026": external_summary,
    }
    _write_clean_json(out_dir / "a4_430_nocontention_benchmark.json", report)
    return report


def run_wave1(
    *,
    parts: Sequence[str] = ("a1", "a2", "a3", "a4"),
    out_dir: Path = DEFAULT_OUT_DIR,
    smoke: bool = False,
) -> dict[str, Any]:
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}

    if "a1" in parts:
        results["a1"] = run_a1_baselines_clean_audit(out_dir, smoke=smoke)
    if "a2" in parts:
        results["a2"] = run_a2_m2_m3_strict_deadline_audit(out_dir, smoke=smoke)
    if "a3" in parts:
        results["a3"] = run_a3_m32_2x2_orthogonal(out_dir, smoke=smoke)
    if "a4" in parts:
        results["a4"] = run_a4_430_nocontention(out_dir, a1_report=results.get("a1"), smoke=smoke)

    master = {
        "schema_version": "m6-wave1-master-summary/v1",
        "generated_at": _utc_now(),
        "smoke": smoke,
        "completed_parts": sorted(results.keys()),
        "leakage_check": "passed_recursive_scan",
        "a1_highlights": {
            "uncensored_overrun_anomalies_count": results["a1"]["uncensored_overrun_anomalies_count"],
            "censored_callback_overrun_total": results["a1"]["censored_callback_overrun_total"],
        } if "a1" in results else None,
        "a2_highlights": {
            "m3_25ms_strict_common": results["a2"]["m3"]["tight_25ms"]["strict_common_completed_count"],
            "m2_25ms_strict_common": results["a2"]["m2"]["tight_25ms"]["strict_common_completed_count"],
        } if "a2" in results else None,
        "a3_highlights": results["a3"]["orthogonal_contrasts"] if "a3" in results else None,
        "a4_highlights": {
            "golden_parity": results["a4"]["golden_parity_vs_baselines_2026_sbs"],
            "m32_set_x_nocontention_focus": results["a4"]["m32_set_x_nocontention_focus"],
        } if "a4" in results else None,
    }
    _write_clean_json(out_dir / "wave1_master_summary.json", master)
    return master


def main() -> None:
    parser = argparse.ArgumentParser(description="Wave 1 (0-API) clean audit & no-contention re-evaluation.")
    parser.add_argument("--parts", default="a1,a2,a3,a4", help="Comma-separated subset of a1,a2,a3,a4")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--smoke", action="store_true", help="Fast smoke test with tiny subset and 200 bootstrap draws")
    args = parser.parse_args()
    parts = tuple(p.strip().lower() for p in args.parts.split(",") if p.strip())
    master = run_wave1(parts=parts, out_dir=args.out_dir, smoke=args.smoke)
    print(json.dumps({
        "status": "ok",
        "completed_parts": master["completed_parts"],
        "a1_highlights": master["a1_highlights"],
        "a2_highlights": master["a2_highlights"],
    }, indent=2))


if __name__ == "__main__":
    main()
