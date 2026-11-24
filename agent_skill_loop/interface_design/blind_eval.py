"""Milestone 2 Phase 2C: Pre-blind protocol freezing, one-shot unsealing & evaluation of
``cvrp_m2_blind_120``, paired statistical tests (Wilcoxon signed-rank + 10,000-draw Bootstrap),
Protocol T1 vs T2 budget-adaptation verification, and Direction-2 cross-paradigm selection.

Audit & Blind-Test Discipline:
1. ``freeze_pre_blind_protocol`` freezes and hashes the entire candidate solver roster,
   Direction-2 portfolios, failure-handling rules, denominators, and hypothesis tests
   before the custody-held instance file is loaded.
2. ``unseal_and_verify_m2_blind_suite`` verifies all 120 instance SHA-256 hashes and
   ``suite_content_sha256`` against the public commitment
   ``benchmarks/cvrp_workbench/manifests/cvrp_m2_blind_120_commitment.json``.
3. Exported evaluation reports and release bundles NEVER contain raw coordinates, demands,
   or ``sealed_seed_token`` from ``cvrp_m2_blind_120``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.protocol import extract_instance_features
from agent_skill_loop.cvrp_workbench.runner import aggregate_records
from agent_skill_loop.cvrp_workbench.selection import (
    evaluate_frozen_transfer_portfolio,
    evaluate_oof_portfolio,
)
from agent_skill_loop.cvrp_workbench.solvers import (
    SOLVER_CATALOG,
    evaluate_algorithm_on_instance,
)
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID

from .blind_commitment import (
    BLIND_COMMITMENT_PATH,
    SEALED_BLIND_SUITE_ID,
    read_public_blind_commitment,
    read_verified_blind_payload,
    require_external_custody_path,
)
from .blind_eval_m32 import (
    freeze_m32_roster_lock,
    freeze_pre_blind_protocol_m32,
    seal_m31_blind_suite,
    seal_m32_blind_120,
    unseal_and_evaluate_m31,
    unseal_and_evaluate_m32,
)
from .contracts import FrozenInterfaceSolver, canonical_json, classify_outcome, sha256_text
from .runtime import evaluate_frozen_interface_solver
from .templates import get_template_spec

_REPO = Path(__file__).resolve().parents[2]

REFERENCE_BASELINE_IDS: tuple[str, ...] = (
    "nn",
    "s2_r5_spiral",
    "s2_r4_cos",
    "i605_cvrp_c1_tworegime",
    "cw_parallel_merge",
    "cw_relocate_2opt",
)
STANDARD_ARM_SEED_IDS = {
    arm: tuple(f"m2_2b_standard_500ms_{arm}_s{seed}" for seed in (20261122, 20261123))
    for arm in ("fixed_pointwise", "dev_fixed_strong", "short_pilot_racing",
                "diagnostic_rule_planner", "llm_diagnostic_planner")
}
TIGHT_SOLVER_IDS = (
    "m2_2b_tight_25ms_fixed_pointwise_s20261122",
    "m2_2b_tight_25ms_short_pilot_racing_s20261122",
    "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
    "m2_2b_tight_25ms_llm_diagnostic_planner_s20261122",
    "m2_2b_standard_500ms_diagnostic_rule_planner_s20261122",
    "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123",
    "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
    "m2_2b_l2b_ctrl_static_refresh",
    "m2_2b_l2a_evolved_s20261122",
    "m2_2b_l2b_evolved_s20261122",
)


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def paired_wilcoxon_signed_rank(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    """Two-sided Wilcoxon signed-rank test on paired observations ``x - y`` (pure NumPy + math).

    Includes tie correction on average ranks and continuity correction on the normal Z-statistic.
    """
    arr_x = np.asarray(x, dtype=np.float64)
    arr_y = np.asarray(y, dtype=np.float64)
    if arr_x.shape != arr_y.shape or arr_x.ndim != 1:
        raise ValueError("paired_wilcoxon_shape_mismatch")
    diffs = arr_x - arr_y
    nonzero_mask = np.abs(diffs) > 1e-12
    d_nz = diffs[nonzero_mask]
    n_pairs = int(arr_x.size)
    n_nz = int(d_nz.size)
    if n_nz == 0:
        return {
            "n_pairs": n_pairs,
            "n_nonzero": 0,
            "w_plus": 0.0,
            "w_minus": 0.0,
            "z_stat": 0.0,
            "p_two_sided": 1.0,
        }

    abs_d = np.abs(d_nz)
    order = np.argsort(abs_d, kind="mergesort")
    sorted_abs = abs_d[order]
    ranks = np.empty(n_nz, dtype=np.float64)
    tie_Counts: list[int] = []

    i = 0
    while i < n_nz:
        j = i + 1
        while j < n_nz and abs(sorted_abs[j] - sorted_abs[i]) <= 1e-12:
            j += 1
        # 1-based average rank for ties
        avg_rank = 0.5 * ((i + 1) + j)
        ranks[order[i:j]] = avg_rank
        if j - i > 1:
            tie_Counts.append(j - i)
        i = j

    w_plus = float(np.sum(ranks[d_nz > 0]))
    w_minus = float(np.sum(ranks[d_nz < 0]))
    w_stat = min(w_plus, w_minus)

    mean_w = n_nz * (n_nz + 1) / 4.0
    tie_corr = sum(t * (t * t - 1) for t in tie_Counts) / 48.0
    var_w = (n_nz * (n_nz + 1) * (2 * n_nz + 1)) / 24.0 - tie_corr
    if var_w <= 1e-12:
        return {
            "n_pairs": n_pairs,
            "n_nonzero": n_nz,
            "w_plus": round(w_plus, 4),
            "w_minus": round(w_minus, 4),
            "z_stat": 0.0,
            "p_two_sided": 1.0,
        }
    # Continuity-corrected Z
    z = (abs(w_stat - mean_w) - 0.5) / math.sqrt(var_w)
    z = max(0.0, z)
    p_two_sided = math.erfc(z / math.sqrt(2.0))
    return {
        "n_pairs": n_pairs,
        "n_nonzero": n_nz,
        "w_plus": round(w_plus, 4),
        "w_minus": round(w_minus, 4),
        "z_stat": round(float(z), 4),
        "p_two_sided": float(p_two_sided),
    }


def paired_bootstrap_comparison(
    candidate_costs: Sequence[float],
    baseline_costs: Sequence[float],
    *,
    n_boot: int = 10000,
    seed: int = 20261123,
) -> dict[str, Any]:
    """Paired comparison of ``candidate`` vs ``baseline`` (lower cost is better)."""
    cand = np.asarray(candidate_costs, dtype=np.float64)
    base = np.asarray(baseline_costs, dtype=np.float64)
    if cand.shape != base.shape or cand.ndim != 1:
        raise ValueError("paired_bootstrap_shape_mismatch")
    n = int(cand.size)
    cand_mean = float(np.mean(cand))
    base_mean = float(np.mean(base))
    mean_diff = cand_mean - base_mean
    # Positive rel_gain_pct means candidate has LOWER total tour length than baseline
    rel_gain_pct = 100.0 * (float(base.sum()) - float(cand.sum())) / max(float(base.sum()), 1e-12)
    per_inst_rel_pct = 100.0 * (base - cand) / np.maximum(base, 1e-12)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_cand = cand[idx].sum(axis=1)
    boot_base = base[idx].sum(axis=1)
    boot_gain_pct = 100.0 * (boot_base - boot_cand) / np.maximum(boot_base, 1e-12)
    ci_lo, ci_hi = np.quantile(boot_gain_pct, [0.025, 0.975])
    p_one_sided = float(np.mean(boot_gain_pct <= 0.0))

    wins = int(np.sum(cand < base - 1e-12))
    losses = int(np.sum(cand > base + 1e-12))
    ties = n - wins - losses

    wilcoxon = paired_wilcoxon_signed_rank(cand, base)
    return {
        "n_instances": n,
        "candidate_mean": round(cand_mean, 4),
        "baseline_mean": round(base_mean, 4),
        "candidate_total": round(float(cand.sum()), 4),
        "baseline_total": round(float(base.sum()), 4),
        "mean_diff_cand_minus_base": round(mean_diff, 4),
        "rel_gain_vs_baseline_pct": round(rel_gain_pct, 4),
        "per_instance_mean_rel_gain_pct": round(float(np.mean(per_inst_rel_pct)), 4),
        "rel_gain_ci95_pct": [round(float(ci_lo), 4), round(float(ci_hi), 4)],
        "p_boot_one_sided": round(p_one_sided, 6),
        "wilcoxon_signed_rank": wilcoxon,
        "wtl_candidate_vs_baseline": {"wins": wins, "ties": ties, "losses": losses},
    }


def load_phase2b_frozen_roster(
    repo_root: Path = _REPO, *, archive_paths: Sequence[Path] = (),
) -> list[FrozenInterfaceSolver]:
    """Load the complete deduplicated set of frozen M2 solvers from Phase 2B archives."""
    attr_arch = repo_root / "experiments" / "milestone2" / "phase2b_l2_attribution" / "archive" / "archive_manifest.json"
    four_arch = repo_root / "experiments" / "milestone2" / "phase2b_four_arm" / "archive" / "archive_manifest.json"

    by_id: dict[str, FrozenInterfaceSolver] = {}
    for path in archive_paths or (attr_arch, four_arch):
        if not path.is_file():
            raise FileNotFoundError(f"missing_phase2b_archive:{path}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("solvers", []):
            fs = FrozenInterfaceSolver.from_dict(row["frozen_solver"])
            tpl = get_template_spec(fs.template_id, fs.template_version)
            if (fs.template_source_sha256 != tpl.template_source_sha256 or fs.hook_name != tpl.hook_name
                    or sha256_text(fs.hook_code) != fs.hook_code_sha256):
                raise ValueError(f"invalid_frozen_solver_identity:{fs.solver_id}")
            if fs.solver_id in by_id and by_id[fs.solver_id] != fs:
                raise ValueError(f"conflicting_frozen_solver_id:{fs.solver_id}")
            by_id[fs.solver_id] = fs
    required = {sid for pair in STANDARD_ARM_SEED_IDS.values() for sid in pair}
    required.update(TIGHT_SOLVER_IDS)
    if missing := required - by_id.keys():
        raise ValueError(f"incomplete_phase2b_roster:{sorted(missing)}")
    return list(by_id.values())


def freeze_pre_blind_protocol(
    out_path: Path,
    *,
    repo_root: Path = _REPO,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    archive_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    """Freeze and hash the entire Phase 2C evaluation & selection protocol BEFORE unsealing blind instances."""
    commitment_bytes = Path(commitment_path).read_bytes()
    commitment_sha256 = _sha256_bytes(commitment_bytes)
    commitment_doc = read_public_blind_commitment(commitment_path, expected_sha256=commitment_sha256)
    frozen_m2 = load_phase2b_frozen_roster(repo_root, archive_paths=archive_paths)

    ref_specs = []
    for aid in REFERENCE_BASELINE_IDS:
        spec = SOLVER_CATALOG[aid]
        ref_specs.append({
            "algorithm_id": aid,
            "display_name": spec.display_name,
            "paradigm": spec.paradigm,
            "interface": spec.interface,
            "code_sha256": spec.code_sha256,
            "kb_entry_id": spec.kb_entry_id,
        })

    m2_specs = []
    for fs in frozen_m2:
        m2_specs.append({
            "solver_id": fs.solver_id,
            "display_name": fs.display_name,
            "paradigm": fs.paradigm,
            "template_id": fs.template_id,
            "template_version": fs.template_version,
            "template_source_sha256": fs.template_source_sha256,
            "hook_name": fs.hook_name,
            "hook_code_sha256": fs.hook_code_sha256,
            "frozen_solver_sha256": _sha256_bytes(canonical_json(fs.to_dict()).encode("utf-8")),
            "postprocess_mode": fs.postprocess_mode,
            "design_sha256": fs.design_sha256,
            "default_budget_ms": fs.default_budget_ms,
        })

    # Pre-declared Direction-2 portfolios (trained strictly on cvrp_select_multiscale_64)
    portfolios = {
        "m15_pointwise_pool": {
            "description": "Milestone 1/1.5 single-paradigm evolved pointwise constructive pool (R5, R4, Island605 C1).",
            "members": ["s2_r5_spiral", "s2_r4_cos", "i605_cvrp_c1_tworegime"],
        },
        "m2_evolved_cross_paradigm_pool": {
            "description": "Milestone 2 purely evolved cross-paradigm pool combining M1/M1.5 pointwise rules with M2 evolved static (L2a) and dynamic (L2b) parallel-merge solvers.",
            "members": [
                "s2_r5_spiral",
                "i605_cvrp_c1_tworegime",
                "m2_2b_standard_500ms_dev_fixed_strong_s20261122",
                "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123",
                "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
                "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
            ],
        },
        "m2_full_hybrid_pool": {
            "description": "Full cross-paradigm hybrid pool combining classical bare CW + M1/M1.5 pointwise + M2 evolved L2a/L2b parallel-merge solvers.",
            "members": [
                "s2_r5_spiral",
                "i605_cvrp_c1_tworegime",
                "cw_parallel_merge",
                "m2_2b_standard_500ms_dev_fixed_strong_s20261122",
                "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123",
                "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
                "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
            ],
        },
    }

    protocol_payload = {
        "schema_version": "m2-phase2c-pre-blind-protocol/v1",
        "frozen_at": _utc_now(),
        "blind_commitment": {
            "suite_id": commitment_doc["suite_id"],
            "instance_count": commitment_doc["instance_count"],
            "commitment_file_sha256": commitment_sha256,
            "suite_content_sha256": commitment_doc["suite_content_sha256"],
            "generator_version": commitment_doc["generator_version"],
            "generator_source_sha256": commitment_doc["generator_source_sha256"],
        },
        "evaluation_budgets": [
            {
                "budget_id": "standard_500ms",
                "time_budget_ms": 500.0,
                "protocol_role": "Primary full-roster zero-shot blind evaluation (Protocol T2) & Direction-2 cross-paradigm selection.",
            },
            {
                "budget_id": "tight_25ms",
                "time_budget_ms": 25.0,
                "protocol_role": "Target-budget-aware adaptation verification (Protocol T1: 25ms-adapted Arm 4a/4b [L2a] vs Protocol T2: 500ms-selected Arm 4a [L2b] transferred directly to 25ms).",
            },
        ],
        "reference_baselines": ref_specs,
        "frozen_m2_solvers": m2_specs,
        "direction2_selection_protocol": {
            "train_suite_id": "cvrp_select_multiscale_64",
            "test_suite_ids": ["cvrp_m2_blind_120", "cvrp_final_accept_120"],
            "oof_protocols_on_select_64": ["cv12", "loro48", "loso3"],
            "selectors_evaluated": [
                "fixed_best_sbs",
                "stump_1d",
                "knn5",
                "ridge",
                "pairwise_cs",
                "pairwise_plain",
                "rf_reg",
                "rf_pairwise_cs",
            ],
            "failure_handling_rule": "If a member solver fails or times out without an incumbent on an instance, substitute the training SBS solver's valid tour_length and solve_ms and record the fallback.",
            "reported_denominators": [
                "gap_over_sbs_pct = (SBS - VBS) / SBS * 100",
                "gap_over_vbs_pct = (SBS - VBS) / VBS * 100",
            ],
            "portfolios": portfolios,
        },
        "pre_declared_hypothesis_tests": [
            {
                "test_id": "H1_llm_planner_vs_fixed_pointwise_500ms",
                "description": "Arm 4b LLM diagnostic planner (L2a) vs Arm 1 fixed pointwise evolution (L1) across paired seeds on cvrp_m2_blind_120 at 500ms.",
            },
            {
                "test_id": "H2_llm_planner_vs_best_m15_pointwise_c1_500ms",
                "description": "Arm 4b LLM diagnostic planner (s20261123, select_64 winner) vs M1.5 strongest pointwise rule i605_cvrp_c1_tworegime on cvrp_m2_blind_120 at 500ms.",
            },
            {
                "test_id": "H3_llm_planner_vs_rule_planner_500ms",
                "description": "Arm 4b LLM diagnostic planner (picked L2a) vs Arm 4a deterministic rule planner (picked L2b) across paired seeds on cvrp_m2_blind_120 at 500ms.",
            },
            {
                "test_id": "H4_protocol_t1_vs_t2_budget_adaptation_25ms",
                "description": "Protocol T1 (25ms-adapted Arm 4a/4b selecting L2a) vs Protocol T2 (500ms Arm 4a L2b transferred zero-shot to 25ms) on cvrp_m2_blind_120 at 25ms.",
            },
            {
                "test_id": "H5_l2_three_way_attribution_blind120",
                "description": "Controlled 3-way attribution (L2a static vs L2b-ctrl dynamic refresh + static CW vs L2b dynamic state feedback) on cvrp_m2_blind_120 at 500ms and 25ms.",
            },
        ],
        "infrastructure_rerun_policy": "Strictly one-shot evaluation on unsealed cvrp_m2_blind_120; no hyperparameter, prompt, or candidate changes permitted after unsealing.",
    }

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(protocol_payload, ensure_ascii=False, indent=2) + "\n"
    with out_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    protocol_sha = _sha256_bytes(out_path.read_bytes())
    return {
        "protocol_path": str(out_path),
        "protocol_sha256": protocol_sha,
        "protocol": protocol_payload,
    }


def unseal_and_verify_m2_blind_suite(
    *,
    sealed_path: Path,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    expected_commitment_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify the isolated sealed blind file against its public commitment and load instances in memory."""
    commitment_sha256 = expected_commitment_sha256 or _sha256_bytes(Path(commitment_path).read_bytes())
    sealed_doc, commitment_doc, verification = read_verified_blind_payload(
        sealed_path=sealed_path,
        commitment_path=commitment_path,
        expected_commitment_sha256=commitment_sha256,
    )
    suite = {
        "suite_id": SEALED_BLIND_SUITE_ID,
        "benchmark_id": BENCHMARK_ID,
        "problem_family": "cvrp",
        "benchmark_tier": "local_controlled",
        "split": "heldout",
        "suite_role": "final_blind_acceptance",
        "exposure_status": "unsealed_one_shot_phase2c",
        "distance_convention": sealed_doc["distance_convention"],
        "vehicle_limit_policy": sealed_doc["vehicle_limit_policy"],
        "data_manifest_hash": commitment_doc["suite_content_sha256"],
        "reference_manifest_hash": commitment_doc["suite_content_sha256"],
        "benchmark_spec_hash": commitment_sha256,
        "selection_manifest_hash": None,
        "published_results_path": None,
        "published_results_hash": None,
        "metadata": {
            "generator_version": commitment_doc["generator_version"],
            "generator_source_sha256": commitment_doc["generator_source_sha256"],
            "stratification_spec": commitment_doc["stratification_spec"],
            "commitment_verified": True,
        },
        "instances": sealed_doc["instances"],
        "scale_stress_instances": [],
    }
    return suite, verification


def _evaluate_suite_roster(
    suite: Mapping[str, Any],
    *,
    reference_ids: Sequence[str],
    frozen_solvers: Sequence[FrozenInterfaceSolver],
    budget_id: str,
    time_budget_ms: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Evaluate reference + M2 frozen solvers on one suite and return (records, suite_summary, feature_rows)."""
    suite_id = str(suite.get("suite_id") or suite.get("profile"))
    dist_conv = str(suite["distance_convention"])
    veh_pol = str(suite["vehicle_limit_policy"])
    instances = list(suite["instances"])
    frozen_by_id = {fs.solver_id: fs for fs in frozen_solvers}
    public_routes: dict[str, Any] = {}
    algs_order = [*list(reference_ids), *[fs.solver_id for fs in frozen_solvers]]

    records: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for inst in instances:
        iid = str(inst["instance_id"])
        feats, feat_ms = extract_instance_features(inst)
        frow: dict[str, Any] = {
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

        for alg_id in algs_order:
            if alg_id in frozen_by_id:
                fs = frozen_by_id[alg_id]
                res = evaluate_frozen_interface_solver(
                    fs,
                    inst,
                    distance_convention=dist_conv,
                    vehicle_limit_policy=veh_pol,
                    time_budget_ms=time_budget_ms,
                )
                paradigm = fs.paradigm
                interface_str = f"{fs.template_id}/{fs.template_version}:{fs.hook_name}"
                kb_entry_id = fs.kb_entry_id
            else:
                spec = SOLVER_CATALOG[alg_id]
                res = evaluate_algorithm_on_instance(
                    alg_id,
                    inst,
                    distance_convention=dist_conv,
                    vehicle_limit_policy=veh_pol,
                    time_budget_ms=time_budget_ms,
                    record_trace=False,
                )
                paradigm = spec.paradigm
                interface_str = spec.interface
                kb_entry_id = spec.kb_entry_id

            rec = {
                "suite_id": suite_id,
                "problem_family": "cvrp",
                "benchmark_tier": suite.get("benchmark_tier", "local_controlled"),
                "suite_role": suite.get("suite_role", "final_blind_acceptance"),
                "exposure_status": suite.get("exposure_status", "unsealed_one_shot_phase2c"),
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
                "algorithm_id": alg_id,
                "paradigm": paradigm,
                "interface": interface_str,
                "kb_entry_id": kb_entry_id,
                "status": res["status"],
                "outcome_class": res.get("outcome_class") or classify_outcome(
                    valid=bool(res["valid"]),
                    status=str(res["status"]),
                    budget_exhausted=bool(res.get("budget_exhausted", False)),
                ),
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
                "candidate_gen_ms": res.get("candidate_gen_ms"),
                "hook_ms": res.get("hook_ms"),
                "postprocess_ms": res.get("postprocess_ms"),
                "solve_ms": res["solve_ms"],
                "verify_ms": res["verify_ms"],
                "voluntary_early_return_count": res.get("voluntary_early_return_count", 0),
                "forced_capacity_return_count": res.get("forced_capacity_return_count", 0),
                "budget_exhausted": res["budget_exhausted"],
                "stop_reason": res.get("stop_reason"),
                "has_trace": False,
            }
            records.append(rec)
            if suite_id != SEALED_BLIND_SUITE_ID and alg_id in frozen_by_id and rec["valid"]:
                public_routes.setdefault(iid, {})[alg_id] = {
                    "routes": res["routes"],
                    "route_loads": res["route_loads"],
                    "route_distances": res["route_distances"],
                    "tour_length": rec["tour_length"],
                    "rel_gap": rec["rel_gap"],
                    "voluntary_early_return_count": rec["voluntary_early_return_count"],
                }
            if res["valid"] and res["tour_length"] is not None:
                frow["costs"][alg_id] = float(res["tour_length"])
                frow["solve_ms"][alg_id] = float(res["solve_ms"])
        feature_rows.append(frow)

    ok_ids_by_alg = {
        alg_id: {
            str(r["instance_id"])
            for r in records
            if r["algorithm_id"] == alg_id and r.get("status") == "ok" and r.get("tour_length") is not None
        }
        for alg_id in algs_order
    }
    all_inst_ids = {str(inst["instance_id"]) for inst in instances}
    common_ids = set(all_inst_ids)
    for s_ids in ok_ids_by_alg.values():
        common_ids &= s_ids

    alg_summaries: dict[str, Any] = {}
    for alg_id in algs_order:
        rows_a = [r for r in records if r["algorithm_id"] == alg_id]
        by_scale = {
            str(sz): aggregate_records([r for r in rows_a if int(r["size"]) == sz])
            for sz in sorted({int(r["size"]) for r in rows_a})
        }
        by_spatial = {
            sp: aggregate_records([r for r in rows_a if r.get("spatial") == sp])
            for sp in sorted({str(r["spatial"]) for r in rows_a if r.get("spatial")})
        }
        by_depot = {
            dp: aggregate_records([r for r in rows_a if r.get("depot_style") == dp])
            for dp in sorted({str(r["depot_style"]) for r in rows_a if r.get("depot_style")})
        }
        by_cap = {
            cp: aggregate_records([r for r in rows_a if r.get("capacity_level") == cp])
            for cp in sorted({str(r["capacity_level"]) for r in rows_a if r.get("capacity_level")})
        }
        alg_summaries[alg_id] = {
            "overall": aggregate_records(rows_a),
            "common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in common_ids]),
            "strict_all_common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in common_ids]),
            "by_scale": by_scale,
            "by_spatial": by_spatial,
            "by_depot_style": by_depot,
            "by_capacity_level": by_cap,
        }

    suite_summary = {
        "suite_id": suite_id,
        "problem_family": "cvrp",
        "benchmark_tier": suite.get("benchmark_tier", "local_controlled"),
        "suite_role": suite.get("suite_role", "final_blind_acceptance"),
        "exposure_status": suite.get("exposure_status", "unsealed_one_shot_phase2c"),
        "distance_convention": dist_conv,
        "vehicle_limit_policy": veh_pol,
        "reference_kind": instances[0].get("reference_kind") if instances else "solver_reference",
        "comparison_mode": "local_recomputed",
        "budget_id": budget_id,
        "budget_ms": time_budget_ms,
        "n_instances": len(instances),
        "common_completed_count": len(common_ids),
        "common_completed_algorithms": algs_order,
        "strict_all_common_completed_count": len(common_ids),
        "algorithms": alg_summaries,
    }
    return records, suite_summary, feature_rows, public_routes


def _enrich_portfolio_dual_denominators(analysis: dict[str, Any]) -> dict[str, Any]:
    """Explicitly annotate both (SBS-VBS)/SBS and (SBS-VBS)/VBS denominators per GPT review #2."""
    sbs_tot = float(analysis["global_sbs_total"])
    vbs_tot = float(analysis["global_vbs_total"])
    analysis["global_sbs_gap_over_sbs_pct"] = round(100.0 * (sbs_tot - vbs_tot) / max(sbs_tot, 1e-12), 4)
    analysis["global_sbs_gap_over_vbs_pct"] = round(100.0 * (sbs_tot - vbs_tot) / max(vbs_tot, 1e-12), 4)
    return analysis


def execute_m2_blind_evaluation(
    out_dir: Path,
    *,
    repo_root: Path = _REPO,
    sealed_path: Path,
    protocol_sha256: str,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    archive_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    """Execute the full Phase 2C pre-blind freeze, one-shot blind unsealing, statistical tests, and Direction-2 selection."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # A separate custody step already froze the protocol; execution cannot rewrite it.
    sealed_path = require_external_custody_path(sealed_path, repo_root)
    protocol_bytes = (out_dir / "pre_blind_protocol.json").read_bytes()
    if _sha256_bytes(protocol_bytes) != protocol_sha256:
        raise ValueError("pre_blind_protocol_hash_mismatch")
    protocol = json.loads(protocol_bytes)
    commitment_sha256 = protocol["blind_commitment"]["commitment_file_sha256"]
    commitment = read_public_blind_commitment(commitment_path, expected_sha256=commitment_sha256)
    roster = {row["solver_id"]: row.get("frozen_solver_sha256") for row in protocol["frozen_m2_solvers"]}
    frozen_m2 = load_phase2b_frozen_roster(repo_root, archive_paths=archive_paths)
    if roster != {fs.solver_id: _sha256_bytes(canonical_json(fs.to_dict()).encode("utf-8")) for fs in frozen_m2}:
        raise ValueError("pre_blind_frozen_roster_hash_mismatch")
    for row in protocol["reference_baselines"]:
        if SOLVER_CATALOG[row["algorithm_id"]].code_sha256 != row["code_sha256"]:
            raise ValueError("pre_blind_reference_roster_hash_mismatch")
    previous = repo_root / "experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json"
    if previous.is_file() and json.loads(previous.read_bytes())["commitment_verification"]["suite_content_sha256"] == commitment["suite_content_sha256"]:
        raise FileExistsError("blind_commitment_already_evaluated")
    if any((out_dir / name).exists() for name in (
        "blind_evaluation.started", "blind_120_evaluation_report.json", "publication_input.json",
    )):
        raise FileExistsError("blind_evaluation_output_already_used")
    pre_blind = {"protocol_sha256": protocol_sha256, "protocol": protocol}

    attempt = sealed_path.parent / f".{commitment['suite_content_sha256']}.blind-attempt"
    with attempt.open("x", encoding="utf-8") as handle:
        handle.write(protocol_sha256 + "\n")
    with (out_dir / "blind_evaluation.started").open("x", encoding="utf-8") as handle:
        handle.write(protocol_sha256 + "\n")

    # 2. Unseal and verify cvrp_m2_blind_120 against public commitment
    blind_suite, verification = unseal_and_verify_m2_blind_suite(
        sealed_path=sealed_path,
        commitment_path=commitment_path,
        expected_commitment_sha256=commitment_sha256,
    )
    select64_suite = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    final120_suite = load_profile_suite(BENCHMARK_ID, "cvrp_final_accept_120", split="heldout")
    dev24_suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")

    frozen_by_id = {fs.solver_id: fs for fs in frozen_m2}

    # 3. Evaluate all reference + frozen M2 solvers under standard_500ms across dev_24, select_64, final_accept_120, and cvrp_m2_blind_120
    recs_dev24_500, sum_dev24_500, _, routes_dev24 = _evaluate_suite_roster(
        dev24_suite,
        reference_ids=REFERENCE_BASELINE_IDS,
        frozen_solvers=frozen_m2,
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )
    recs_sel64_500, sum_sel64_500, frows_sel64_500, routes_sel64 = _evaluate_suite_roster(
        select64_suite,
        reference_ids=REFERENCE_BASELINE_IDS,
        frozen_solvers=frozen_m2,
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )
    recs_fa120_500, sum_fa120_500, frows_fa120_500, routes_fa120 = _evaluate_suite_roster(
        final120_suite,
        reference_ids=REFERENCE_BASELINE_IDS,
        frozen_solvers=frozen_m2,
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )
    recs_blind120_500, sum_blind120_500, frows_blind120_500, _ = _evaluate_suite_roster(
        blind_suite,
        reference_ids=REFERENCE_BASELINE_IDS,
        frozen_solvers=frozen_m2,
        budget_id="standard_500ms",
        time_budget_ms=500.0,
    )

    # 4. Evaluate under tight_25ms on cvrp_m2_blind_120 to test Protocol T1 vs Protocol T2
    tight_frozen = [frozen_by_id[sid] for sid in TIGHT_SOLVER_IDS]
    recs_blind120_25, sum_blind120_25, _, _ = _evaluate_suite_roster(
        blind_suite,
        reference_ids=("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge"),
        frozen_solvers=tight_frozen,
        budget_id="tight_25ms",
        time_budget_ms=25.0,
    )

    # 5. Compute paired statistical tests on cvrp_m2_blind_120
    def _costs_map(frows: Sequence[Mapping[str, Any]], aid: str) -> list[float]:
        return [float(r["costs"][aid]) for r in frows]

    costs_25_by_alg: dict[str, list[float]] = {}
    for aid in ("s2_r5_spiral", "i605_cvrp_c1_tworegime", "cw_parallel_merge", *[fs.solver_id for fs in tight_frozen]):
        costs = {
            r["instance_id"]: float(r["tour_length"])
            for r in recs_blind120_25
            if r["algorithm_id"] == aid and r["tour_length"] is not None
        }
        if set(costs) != {r["instance_id"] for r in frows_blind120_500}:
            raise ValueError(f"blind_paired_costs_incomplete:{aid}")
        costs_25_by_alg[aid] = [costs[r["instance_id"]] for r in frows_blind120_500]

    # Paired seed average per instance for 500ms five-arm comparison on blind_120
    arm_avg_costs_blind120: dict[str, list[float]] = {}
    for arm_name, (s1_id, s2_id) in STANDARD_ARM_SEED_IDS.items():
        c1 = np.asarray(_costs_map(frows_blind120_500, s1_id), dtype=np.float64)
        c2 = np.asarray(_costs_map(frows_blind120_500, s2_id), dtype=np.float64)
        arm_avg_costs_blind120[arm_name] = [float(x) for x in (0.5 * (c1 + c2))]

    hypothesis_tests = {
        "H1_llm_planner_vs_fixed_pointwise_500ms_paired_avg": paired_bootstrap_comparison(
            arm_avg_costs_blind120["llm_diagnostic_planner"],
            arm_avg_costs_blind120["fixed_pointwise"],
        ),
        "H2_llm_planner_s20261123_vs_c1_tworegime_500ms": paired_bootstrap_comparison(
            _costs_map(frows_blind120_500, "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"),
            _costs_map(frows_blind120_500, "i605_cvrp_c1_tworegime"),
        ),
        "H2b_llm_planner_s20261123_vs_r5_spiral_500ms": paired_bootstrap_comparison(
            _costs_map(frows_blind120_500, "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"),
            _costs_map(frows_blind120_500, "s2_r5_spiral"),
        ),
        "H3_llm_planner_vs_rule_planner_500ms_paired_avg": paired_bootstrap_comparison(
            arm_avg_costs_blind120["llm_diagnostic_planner"],
            arm_avg_costs_blind120["diagnostic_rule_planner"],
        ),
        "H3b_llm_planner_s20261123_vs_bare_cw_500ms": paired_bootstrap_comparison(
            _costs_map(frows_blind120_500, "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"),
            _costs_map(frows_blind120_500, "cw_parallel_merge"),
        ),
        "H4a_protocol_t1_rule_25ms_vs_t2_rule_500ms_at_25ms": paired_bootstrap_comparison(
            costs_25_by_alg["m2_2b_tight_25ms_diagnostic_rule_planner_s20261122"],
            costs_25_by_alg["m2_2b_standard_500ms_diagnostic_rule_planner_s20261122"],
        ),
        "H4b_protocol_t1_llm_25ms_vs_t2_rule_500ms_at_25ms": paired_bootstrap_comparison(
            costs_25_by_alg["m2_2b_tight_25ms_llm_diagnostic_planner_s20261122"],
            costs_25_by_alg["m2_2b_standard_500ms_diagnostic_rule_planner_s20261122"],
        ),
        "H4c_protocol_t1_rule_25ms_vs_bare_cw_at_25ms": paired_bootstrap_comparison(
            costs_25_by_alg["m2_2b_tight_25ms_diagnostic_rule_planner_s20261122"],
            costs_25_by_alg["cw_parallel_merge"],
        ),
        "H5a_l2a_evolved_vs_l2b_ctrl_at_25ms": paired_bootstrap_comparison(
            costs_25_by_alg["m2_2b_l2a_evolved_s20261122"],
            costs_25_by_alg["m2_2b_l2b_ctrl_static_refresh"],
        ),
        "H5b_l2b_ctrl_vs_bare_cw_at_500ms_exact_equivalence": paired_bootstrap_comparison(
            _costs_map(frows_blind120_500, "m2_2b_l2b_ctrl_static_refresh"),
            _costs_map(frows_blind120_500, "cw_parallel_merge"),
        ),
    }

    # Summarize 5-arm paired performance on cvrp_m2_blind_120 (500ms) and 4-arm on cvrp_m2_blind_120 (25ms)
    blind_500_arm_summary: dict[str, Any] = {}
    for arm_name, (s1_id, s2_id) in arm_seed_pairs_500.items():
        m1 = sum_blind120_500["algorithms"][s1_id]["overall"]
        m2 = sum_blind120_500["algorithms"][s2_id]["overall"]
        blind_500_arm_summary[arm_name] = {
            "seed_20261122_mean": m1["mean_tour_length"],
            "seed_20261123_mean": m2["mean_tour_length"],
            "paired_mean_avg": round(0.5 * (float(m1["mean_tour_length"]) + float(m2["mean_tour_length"])), 4),
            "best_seed_mean": round(min(float(m1["mean_tour_length"]), float(m2["mean_tour_length"])), 4),
            "completion_rate_avg": round(0.5 * (float(m1["completion_rate"]) + float(m2["completion_rate"])), 4),
            "solve_ms_p50_avg": round(0.5 * (float(m1["solve_ms_p50"]) + float(m2["solve_ms_p50"])), 4),
            "solve_ms_p95_avg": round(0.5 * (float(m1["solve_ms_p95"]) + float(m2["solve_ms_p95"])), 4),
        }

    blind_25_arm_summary: dict[str, Any] = {}
    for aid in (
        "cw_parallel_merge",
        "i605_cvrp_c1_tworegime",
        "s2_r5_spiral",
        "m2_2b_tight_25ms_fixed_pointwise_s20261122",
        "m2_2b_tight_25ms_short_pilot_racing_s20261122",
        "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
        "m2_2b_tight_25ms_llm_diagnostic_planner_s20261122",
        "m2_2b_standard_500ms_diagnostic_rule_planner_s20261122",
        "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123",
        "m2_2b_l2b_ctrl_static_refresh",
        "m2_2b_l2a_evolved_s20261122",
        "m2_2b_l2b_evolved_s20261122",
    ):
        ov = sum_blind120_25["algorithms"][aid]["overall"]
        blind_25_arm_summary[aid] = {
            "mean_tour_length": ov["mean_tour_length"],
            "completion_rate": ov["completion_rate"],
            "ok_budget_exhausted_count": ov["ok_budget_exhausted_count"],
            "timeout_count": ov["timeout_count"],
            "solve_ms_p50": ov["solve_ms_p50"],
            "solve_ms_p95": ov["solve_ms_p95"],
            "by_scale_n200_mean": sum_blind120_25["algorithms"][aid]["by_scale"]["200"]["mean_tour_length"],
            "by_scale_n200_budget_exhausted": sum_blind120_25["algorithms"][aid]["by_scale"]["200"]["ok_budget_exhausted_count"],
        }

    # 6. Direction-2 Cross-Paradigm Selection Analyses (OOF on select_64 + Frozen transfer to blind_120 & final_accept_120)
    portfolios_cfg = pre_blind["protocol"]["direction2_selection_protocol"]["portfolios"]
    direction2_analyses: dict[str, Any] = {}
    for pid, pspec in portfolios_cfg.items():
        members = pspec["members"]
        oof_64 = _enrich_portfolio_dual_denominators(
            evaluate_oof_portfolio(
                "cvrp_select_multiscale_64",
                pid,
                frows_sel64_500,
                members,
                protocols=("cv12", "loro48", "loso3"),
            )
        )
        xfer_blind120 = _enrich_portfolio_dual_denominators(
            evaluate_frozen_transfer_portfolio(
                train_suite_id="cvrp_select_multiscale_64",
                test_suite_id="cvrp_m2_blind_120",
                portfolio_id=f"{pid}_frozen_blind120",
                train_rows=frows_sel64_500,
                test_rows=frows_blind120_500,
                members=members,
            )
        )
        xfer_fa120 = _enrich_portfolio_dual_denominators(
            evaluate_frozen_transfer_portfolio(
                train_suite_id="cvrp_select_multiscale_64",
                test_suite_id="cvrp_final_accept_120",
                portfolio_id=f"{pid}_frozen_final120",
                train_rows=frows_sel64_500,
                test_rows=frows_fa120_500,
                members=members,
            )
        )
        direction2_analyses[f"select_64__{pid}"] = oof_64
        direction2_analyses[f"m2_blind_120__{pid}_frozen"] = xfer_blind120
        direction2_analyses[f"final_accept_120__{pid}_frozen"] = xfer_fa120

    # Compact overview table of Direction-2 portfolios on select_64, final_accept_120, and cvrp_m2_blind_120
    direction2_overview: dict[str, Any] = {}
    for key, analysis in direction2_analyses.items():
        proto_key = "frozen_transfer" if "frozen_transfer" in analysis["protocols"] else "cv12"
        sels = analysis["protocols"][proto_key]["selectors"]
        best_learned = min(
            (s for sname, s in sels.items() if sname not in {"oracle_vbs", "fixed_best_sbs"}),
            key=lambda s: float(s["total"]),
        )
        direction2_overview[key] = {
            "suite_id": analysis["suite_id"],
            "portfolio_id": analysis["portfolio_id"],
            "members": analysis["members"],
            "n_instances": analysis["n_instances"],
            "sbs_algorithm": analysis["global_sbs_algorithm"],
            "sbs_total": analysis["global_sbs_total"],
            "sbs_mean": round(float(analysis["global_sbs_total"]) / max(1, int(analysis["n_instances"])), 4),
            "vbs_total": analysis["global_vbs_total"],
            "vbs_mean": round(float(analysis["global_vbs_total"]) / max(1, int(analysis["n_instances"])), 4),
            "gap_over_sbs_pct": analysis["global_sbs_gap_over_sbs_pct"],
            "gap_over_vbs_pct": analysis["global_sbs_gap_over_vbs_pct"],
            "oracle_counts": analysis["oracle_counts"],
            "best_learned_selector_id": best_learned["selector_id"],
            "best_learned_total": best_learned["total"],
            "best_learned_mean": best_learned["mean"],
            "best_learned_gain_vs_sbs_pct": round(float(best_learned["gain_vs_sbs"]) * 100.0, 4),
            "best_learned_ci95_pct": [round(float(x) * 100.0, 4) for x in best_learned["gain_ci95"]],
            "best_learned_wtl_vs_sbs": best_learned["wtl_vs_sbs"],
            "best_learned_total_ms_p50": best_learned["total_ms_p50"],
        }

    blind_report = {
        "schema_version": "m2-phase2c-blind120-evaluation-report/v1",
        "generated_at": _utc_now(),
        "pre_blind_protocol_sha256": pre_blind["protocol_sha256"],
        "commitment_verification": verification,
        "blind_120_standard_500ms_arm_summary": blind_500_arm_summary,
        "blind_120_tight_25ms_summary": blind_25_arm_summary,
        "hypothesis_tests_blind_120": hypothesis_tests,
        "direction2_overview": direction2_overview,
        "suite_summaries_500ms": {
            "cvrp_dev_hetero_24": sum_dev24_500,
            "cvrp_select_multiscale_64": sum_sel64_500,
            "cvrp_final_accept_120": sum_fa120_500,
            "cvrp_m2_blind_120": sum_blind120_500,
        },
        "suite_summaries_25ms": {
            "cvrp_m2_blind_120": sum_blind120_25,
        },
    }

    (out_dir / "blind_120_evaluation_report.json").write_text(
        json.dumps(blind_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out_dir / "direction2_cross_paradigm_report.json").write_text(
        json.dumps(
            {
                "schema_version": "m2-phase2c-direction2-report/v1",
                "generated_at": _utc_now(),
                "pre_blind_protocol_sha256": pre_blind["protocol_sha256"],
                "overview": direction2_overview,
                "analyses": direction2_analyses,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {
        "blind_report": blind_report,
        "direction2_analyses": direction2_analyses,
        "records_500ms": {
            "cvrp_dev_hetero_24": recs_dev24_500,
            "cvrp_select_multiscale_64": recs_sel64_500,
            "cvrp_final_accept_120": recs_fa120_500,
            "cvrp_m2_blind_120": recs_blind120_500,
        },
        "records_25ms": {
            "cvrp_m2_blind_120": recs_blind120_25,
        },
        "public_routes_500ms": {
            "cvrp_dev_hetero_24": routes_dev24,
            "cvrp_select_multiscale_64": routes_sel64,
            "cvrp_final_accept_120": routes_fa120,
        },
        "feature_rows_blind120_500": frows_blind120_500,
        "frozen_m2_solvers": frozen_m2,
    }
