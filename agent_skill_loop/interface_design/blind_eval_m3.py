"""Milestone 3 Phase 3D: Pre-blind protocol freezing, one-shot unsealing & evaluation of
``cvrp_m3_blind_120``, per-seed paired statistical tests with Holm-Bonferroni correction,
external top-venue / OR gold-standard benchmarks (EoH-S 256, CVRPLib A/B/P 74, Set X 100),
and Direction-2 cross-paradigm selection.

Audit & Blind-Test Discipline:
1. ``freeze_m3_pre_blind_protocol`` freezes and hashes every reference, M2, and M3 solver,
   external roster, Direction-2 portfolio, penalized failure rule, and hypothesis family
   BEFORE opening the custody-held ``cvrp_m3_blind_120_sealed.json`` file.
2. ``unseal_and_verify_m3_blind_suite`` verifies all 120 instance SHA-256 digests and
   ``suite_content_sha256`` against ``cvrp_m3_blind_120_commitment.json`` (`11c0f9ca...`).
3. Per-seed statistical inference evaluates each random seed independently over the fixed
   120 blind instances (never pooling 3x120 as 360 independent trials) and applies
   Holm-Bonferroni step-down adjustment across each pre-registered test family.
4. Exported reports and release bundles NEVER contain raw blind coordinates, demands,
   or ``sealed_seed_token``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
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
    M3_BLIND_COMMITMENT_PATH,
    SEALED_M3_BLIND_SUITE_ID,
    read_public_blind_commitment,
    read_verified_blind_payload,
    require_external_custody_path,
)
from .blind_eval import (
    REFERENCE_BASELINE_IDS,
    load_phase2b_frozen_roster,
    paired_bootstrap_comparison,
)
from .contracts import FrozenInterfaceSolver, canonical_json, classify_outcome, sha256_text
from .runtime import evaluate_frozen_interface_solver
from .templates import get_template_spec

_REPO = Path(__file__).resolve().parents[2]

PHASE3C_SEEDS: tuple[int, ...] = (20261124, 20261125, 20261126)
PHASE3C_ARMS: tuple[str, ...] = (
    "arm_m3_0_pure_eoh",
    "arm_m3_1_plain_text",
    "arm_m3_2_fixed_l2a",
    "arm_m3_3_full_dynamic",
)
M3_EXTRA_L3_SOLVER_ID = "m3_3c_standard_500ms_arm_m3_3_r2_l3_evolved_s20261124"
M3_EXTRA_L3_RELPATH = (
    Path("experiments")
    / "milestone3"
    / "phase3c_four_arm"
    / "standard_500ms"
    / "seed_20261124"
    / "arm_m3_3_full_dynamic"
    / "agent_artifacts"
    / "round_0002_frozen_solver.json"
)
M2_COMPARE_IDS: tuple[str, ...] = (
    "m2_2b_standard_500ms_dev_fixed_strong_s20261122",
    "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123",
    "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
    "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
)
EXTERNAL_REF_IDS: tuple[str, ...] = (
    "nn",
    "s2_r5_spiral",
    "i605_cvrp_c1_tworegime",
    "cw_parallel_merge",
    "cw_relocate_2opt",
)
EXTERNAL_M2_IDS: tuple[str, ...] = (
    "m2_2b_standard_500ms_dev_fixed_strong_s20261122",
    "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
)


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def holm_bonferroni_adjust(p_values: Sequence[float]) -> list[float]:
    """Compute step-down Holm-Bonferroni adjusted p-values preserving original index order."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(float(p) for p in p_values), key=lambda item: item[1])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p_val) in enumerate(indexed):
        scaled = (m - rank) * p_val
        running_max = min(1.0, max(running_max, scaled))
        adjusted[orig_idx] = round(float(running_max), 8)
    return adjusted


def _verify_frozen_solver(fs: FrozenInterfaceSolver) -> None:
    tpl = get_template_spec(fs.template_id, fs.template_version)
    if (
        fs.template_source_sha256 != tpl.template_source_sha256
        or fs.hook_name != tpl.hook_name
        or sha256_text(fs.hook_code) != fs.hook_code_sha256
    ):
        raise ValueError(f"invalid_frozen_solver_identity:{fs.solver_id}")


def load_phase3c_frozen_roster(repo_root: Path = _REPO) -> list[FrozenInterfaceSolver]:
    """Load and verify all Phase 3C frozen arm solvers, L3-ctrl baselines, M3 R2 L3, and M2 comparators."""
    arch_path = repo_root / "experiments" / "milestone3" / "phase3c_four_arm" / "archive" / "archive_manifest.json"
    if not arch_path.is_file():
        raise FileNotFoundError(f"missing_phase3c_archive:{arch_path}")

    by_id: dict[str, FrozenInterfaceSolver] = {}
    doc = json.loads(arch_path.read_text(encoding="utf-8"))
    for row in doc.get("solvers", []):
        fs = FrozenInterfaceSolver.from_dict(row["frozen_solver"])
        _verify_frozen_solver(fs)
        if fs.solver_id in by_id and by_id[fs.solver_id] != fs:
            raise ValueError(f"conflicting_m3_frozen_solver:{fs.solver_id}")
        by_id[fs.solver_id] = fs

    # Add Round-2 evolved L3 stepping stone from seed_20261124/arm_m3_3_full_dynamic
    r2_l3_path = repo_root / M3_EXTRA_L3_RELPATH
    if not r2_l3_path.is_file():
        raise FileNotFoundError(f"missing_m3_r2_l3_solver:{r2_l3_path}")
    r2_raw = json.loads(r2_l3_path.read_text(encoding="utf-8"))
    r2_raw["solver_id"] = M3_EXTRA_L3_SOLVER_ID
    r2_raw["display_name"] = "M3 arm_m3_3 R2 Evolved L3 (s20261124, 500ms)"
    r2_fs = FrozenInterfaceSolver.from_dict(r2_raw)
    _verify_frozen_solver(r2_fs)
    by_id[r2_fs.solver_id] = r2_fs

    # Add representative frozen M2 comparators
    m2_all = {fs.solver_id: fs for fs in load_phase2b_frozen_roster(repo_root)}
    for m2_id in M2_COMPARE_IDS:
        fs = m2_all[m2_id]
        _verify_frozen_solver(fs)
        by_id[m2_id] = fs

    required: set[str] = {
        *(f"m3_3c_{bid}_{arm}_s{seed}" for bid in ("standard_500ms", "tight_25ms") for seed in PHASE3C_SEEDS for arm in PHASE3C_ARMS),
        "m3_l3_ctrl_500ms",
        "m3_l3_ctrl_25ms",
        M3_EXTRA_L3_SOLVER_ID,
        *M2_COMPARE_IDS,
    }
    if missing := required - by_id.keys():
        raise ValueError(f"incomplete_phase3c_roster:{sorted(missing)}")
    return [by_id[k] for k in sorted(by_id)]


def _build_external_roster_ids(frozen_ids: set[str]) -> list[str]:
    ordered: list[str] = [
        *EXTERNAL_REF_IDS,
        *EXTERNAL_M2_IDS,
        *(f"m3_3c_standard_500ms_{arm}_s{seed}" for seed in PHASE3C_SEEDS for arm in PHASE3C_ARMS),
        "m3_l3_ctrl_500ms",
        M3_EXTRA_L3_SOLVER_ID,
        "m3_3c_tight_25ms_arm_m3_2_fixed_l2a_s20261126",
    ]
    missing = [aid for aid in ordered if aid not in SOLVER_CATALOG and aid not in frozen_ids]
    if missing:
        raise ValueError(f"missing_external_roster_solvers:{missing}")
    return ordered


def _build_tight_roster_ids(frozen_ids: set[str]) -> list[str]:
    ordered: list[str] = [
        "nn",
        "s2_r5_spiral",
        "i605_cvrp_c1_tworegime",
        "cw_parallel_merge",
        "cw_relocate_2opt",
        "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122",
        "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123",
        *(f"m3_3c_tight_25ms_{arm}_s{seed}" for seed in PHASE3C_SEEDS for arm in PHASE3C_ARMS),
        *(f"m3_3c_standard_500ms_arm_m3_3_full_dynamic_s{seed}" for seed in PHASE3C_SEEDS),
        *(f"m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s{seed}" for seed in PHASE3C_SEEDS),
        "m3_l3_ctrl_25ms",
        M3_EXTRA_L3_SOLVER_ID,
    ]
    missing = [aid for aid in ordered if aid not in SOLVER_CATALOG and aid not in frozen_ids]
    if missing:
        raise ValueError(f"missing_tight_roster_solvers:{missing}")
    return ordered


def freeze_m3_pre_blind_protocol(
    out_path: Path,
    *,
    repo_root: Path = _REPO,
    commitment_path: Path = M3_BLIND_COMMITMENT_PATH,
) -> dict[str, Any]:
    """Freeze and hash the entire Phase 3D blind, external, and Direction-2 protocol before unsealing."""
    commitment_bytes = Path(commitment_path).read_bytes()
    commitment_sha256 = _sha256_bytes(commitment_bytes)
    commitment_doc = read_public_blind_commitment(
        commitment_path,
        expected_sha256=commitment_sha256,
        expected_suite_id=SEALED_M3_BLIND_SUITE_ID,
    )
    frozen_solvers = load_phase3c_frozen_roster(repo_root)
    frozen_ids = {fs.solver_id for fs in frozen_solvers}

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

    frozen_specs = []
    for fs in frozen_solvers:
        frozen_specs.append({
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

    portfolios = {
        "m15_pointwise_pool": {
            "description": "Milestone 1/1.5 single-paradigm pointwise constructive pool (R5, R4, Island605 C1).",
            "members": ["s2_r5_spiral", "s2_r4_cos", "i605_cvrp_c1_tworegime"],
        },
        "m2_full_hybrid_pool": {
            "description": "Milestone 2 full cross-paradigm hybrid pool (R5, C1, CW, M2 L2a/L2b).",
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
        "m3_evolved_cross_paradigm_pool": {
            "description": "Milestone 3 purely evolved cross-paradigm pool (L1 R5/C1 + M3 L2a+relocate_2opt + M3-3 R2 evolved L3).",
            "members": [
                "s2_r5_spiral",
                "i605_cvrp_c1_tworegime",
                "m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126",
                "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125",
                M3_EXTRA_L3_SOLVER_ID,
                "m3_3c_tight_25ms_arm_m3_2_fixed_l2a_s20261126",
            ],
        },
        "m3_full_hybrid_pool": {
            "description": "Full Milestone 3 cross-paradigm hybrid pool (L1 R5/C1 + CW + CW+LS + L3-ctrl + M3 evolved L2a & L3).",
            "members": [
                "s2_r5_spiral",
                "i605_cvrp_c1_tworegime",
                "cw_parallel_merge",
                "cw_relocate_2opt",
                "m3_l3_ctrl_500ms",
                "m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126",
                "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125",
                M3_EXTRA_L3_SOLVER_ID,
                "m3_3c_tight_25ms_arm_m3_2_fixed_l2a_s20261126",
            ],
        },
    }

    external_roster = _build_external_roster_ids(frozen_ids)
    tight_roster = _build_tight_roster_ids(frozen_ids)

    protocol_payload = {
        "schema_version": "m3-phase3d-pre-blind-protocol/v1",
        "frozen_at": _utc_now(),
        "blind_commitment": {
            "suite_id": commitment_doc["suite_id"],
            "instance_count": commitment_doc["instance_count"],
            "commitment_file_sha256": commitment_sha256,
            "suite_content_sha256": commitment_doc["suite_content_sha256"],
            "generator_version": commitment_doc["generator_version"],
            "generator_source_sha256": commitment_doc["generator_source_sha256"],
        },
        "seeds": list(PHASE3C_SEEDS),
        "arms": list(PHASE3C_ARMS),
        "evaluation_budgets": [
            {
                "budget_id": "standard_500ms",
                "time_budget_ms": 500.0,
                "role": "Primary multi-seed blind evaluation, Section 5.3 backbone/anytime comparison, external benchmarks & Direction-2.",
            },
            {
                "budget_id": "tight_25ms",
                "time_budget_ms": 25.0,
                "role": "Budget-aware adaptation vs direct transfer and L3 timeout-avoidance test on cvrp_m3_blind_120.",
            },
        ],
        "reference_baselines": ref_specs,
        "frozen_solvers": frozen_specs,
        "external_benchmark_suites_500ms": [
            "cvrp_ext_eohs_256",
            "cvrp_ext_cvrplib_abp_74",
            "cvrp_ext_cvrplib_x_100",
        ],
        "external_benchmark_roster_ids": external_roster,
        "tight_25ms_blind_roster_ids": tight_roster,
        "failure_scoring_rule": {
            "penalized_cost_if_invalid_or_none": "2.0 * reference_objective (consistent with M3 dev penalized scoring)",
            "reporting_requirement": "Always report raw completion_rate, ok_budget_exhausted_count, and timeout_count alongside penalized cost.",
        },
        "statistical_protocol": {
            "unit_of_replication": "Per-seed paired over the exact 120 blind instances; NEVER pool 3x120 as 360 independent trials.",
            "per_instance_tests": [
                "Two-sided Wilcoxon signed-rank test with tie & continuity correction",
                "10,000-draw paired Bootstrap 95% CI on relative percentage gain (cand vs base)",
            ],
            "multiple_testing_correction": "Holm-Bonferroni step-down adjusted p-values (p_holm_wilcoxon) per pre-registered hypothesis family.",
        },
        "direction2_selection_protocol": {
            "train_suite_id": "cvrp_select_multiscale_64",
            "test_suite_ids": [SEALED_M3_BLIND_SUITE_ID, "cvrp_final_accept_120"],
            "oof_protocols_on_select_64": ["cv12", "loro48", "loso3"],
            "reported_denominators": [
                "gap_over_sbs_pct = (SBS - VBS) / SBS * 100",
                "gap_over_vbs_pct = (SBS - VBS) / VBS * 100",
            ],
            "portfolios": portfolios,
        },
        "infrastructure_rerun_policy": "Strictly one-shot evaluation on unsealed cvrp_m3_blind_120; zero search/prompt/hyperparameter changes after unsealing.",
    }

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(protocol_payload, ensure_ascii=False, indent=2) + "\n"
    with out_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return {
        "protocol_path": str(out_path),
        "protocol_sha256": _sha256_bytes(out_path.read_bytes()),
        "protocol": protocol_payload,
    }


def unseal_and_verify_m3_blind_suite(
    *,
    sealed_path: Path,
    commitment_path: Path = M3_BLIND_COMMITMENT_PATH,
    expected_commitment_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify custody-held cvrp_m3_blind_120 against public commitment and return in-memory suite."""
    comm_sha = expected_commitment_sha256 or _sha256_bytes(Path(commitment_path).read_bytes())
    sealed_doc, commitment_doc, verification = read_verified_blind_payload(
        sealed_path=sealed_path,
        commitment_path=commitment_path,
        expected_commitment_sha256=comm_sha,
    )
    if commitment_doc["suite_id"] != SEALED_M3_BLIND_SUITE_ID:
        raise ValueError(f"unexpected_m3_blind_suite_id:{commitment_doc['suite_id']}")
    suite = {
        "suite_id": SEALED_M3_BLIND_SUITE_ID,
        "benchmark_id": BENCHMARK_ID,
        "problem_family": "cvrp",
        "benchmark_tier": "local_controlled",
        "split": "heldout",
        "suite_role": "final_blind_acceptance",
        "exposure_status": "unsealed_one_shot_phase3d",
        "distance_convention": sealed_doc["distance_convention"],
        "vehicle_limit_policy": sealed_doc["vehicle_limit_policy"],
        "data_manifest_hash": commitment_doc["suite_content_sha256"],
        "reference_manifest_hash": commitment_doc["suite_content_sha256"],
        "benchmark_spec_hash": comm_sha,
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


def _evaluate_suite_algorithms(
    suite: Mapping[str, Any],
    *,
    algorithm_ids: Sequence[str],
    frozen_by_id: Mapping[str, FrozenInterfaceSolver],
    budget_id: str,
    time_budget_ms: float,
    capture_anytime: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Evaluate a roster on one CVRP suite and return (records, summary, feature_rows, public_routes, anytime_agg)."""
    suite_id = str(suite.get("suite_id") or suite.get("profile"))
    dist_conv = str(suite["distance_convention"])
    veh_pol = str(suite["vehicle_limit_policy"])
    instances = list(suite["instances"])
    is_blind = suite_id == SEALED_M3_BLIND_SUITE_ID

    records: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    public_routes: dict[str, Any] = {}
    anytime_raw: dict[str, dict[str, list[Any]]] = {
        aid: {"first_feasible_ms": [], "curves": []}
        for aid in algorithm_ids
    }

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
            "penalized_costs": {},
            "solve_ms": {},
        }
        ref_obj = inst.get("reference_objective")
        fallback_cost = 2.0 * float(ref_obj) if isinstance(ref_obj, (int, float)) else 1e6

        for alg_id in algorithm_ids:
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
                "exposure_status": suite.get("exposure_status", "unsealed_one_shot_phase3d"),
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
            if not is_blind and alg_id in frozen_by_id and rec["valid"]:
                public_routes.setdefault(iid, {})[alg_id] = {
                    "routes": res["routes"],
                    "route_loads": res["route_loads"],
                    "route_distances": res["route_distances"],
                    "tour_length": rec["tour_length"],
                    "rel_gap": rec["rel_gap"],
                    "voluntary_early_return_count": rec["voluntary_early_return_count"],
                }
            if res["valid"] and res["tour_length"] is not None:
                cost_val = float(res["tour_length"])
                frow["costs"][alg_id] = cost_val
                frow["penalized_costs"][alg_id] = cost_val
                frow["solve_ms"][alg_id] = float(res["solve_ms"])
            else:
                frow["penalized_costs"][alg_id] = fallback_cost
                frow["solve_ms"][alg_id] = float(res.get("solve_ms") or time_budget_ms)

            if capture_anytime and res.get("valid") and res.get("anytime_curve"):
                anytime_raw[alg_id]["curves"].append(res["anytime_curve"])
                if res.get("first_feasible_ms") is not None:
                    anytime_raw[alg_id]["first_feasible_ms"].append(float(res["first_feasible_ms"]))

        feature_rows.append(frow)

    ok_ids_by_alg = {
        aid: {
            str(r["instance_id"])
            for r in records
            if r["algorithm_id"] == aid and r.get("status") == "ok" and r.get("tour_length") is not None
        }
        for aid in algorithm_ids
    }
    all_inst_ids = {str(inst["instance_id"]) for inst in instances}
    strict_common_ids = set(all_inst_ids)
    for s_ids in ok_ids_by_alg.values():
        strict_common_ids &= s_ids

    alg_summaries: dict[str, Any] = {}
    for aid in algorithm_ids:
        rows_a = [r for r in records if r["algorithm_id"] == aid]
        extra: dict[str, Any] = {}
        if suite_id == "cvrp_ext_cvrplib_abp_74":
            extra["by_cvrplib_set"] = {
                cset: aggregate_records([r for r in rows_a if r.get("cvrplib_set") == cset])
                for cset in ("A", "B", "P")
            }
        if suite_id == "cvrp_ext_cvrplib_x_100":
            extra["by_x_tier"] = {
                tier: aggregate_records([r for r in rows_a if r.get("x_tier") == tier])
                for tier in ("X-S (100-250)", "X-M (251-500)", "X-L (501-1000)")
            }
        alg_summaries[aid] = {
            "overall": aggregate_records(rows_a),
            "common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in strict_common_ids]),
            "strict_all_common_completed": aggregate_records([r for r in rows_a if str(r["instance_id"]) in strict_common_ids]),
            "by_scale": {
                str(sz): aggregate_records([r for r in rows_a if int(r["size"]) == sz])
                for sz in sorted({int(r["size"]) for r in rows_a})
            },
            "by_spatial": {
                sp: aggregate_records([r for r in rows_a if r.get("spatial") == sp])
                for sp in sorted({str(r["spatial"]) for r in rows_a if r.get("spatial")})
            },
            "by_depot_style": {
                dp: aggregate_records([r for r in rows_a if r.get("depot_style") == dp])
                for dp in sorted({str(r["depot_style"]) for r in rows_a if r.get("depot_style")})
            },
            "by_capacity_level": {
                cp: aggregate_records([r for r in rows_a if r.get("capacity_level") == cp])
                for cp in sorted({str(r["capacity_level"]) for r in rows_a if r.get("capacity_level")})
            },
            **extra,
        }

    suite_summary = {
        "suite_id": suite_id,
        "problem_family": "cvrp",
        "benchmark_tier": suite.get("benchmark_tier", "local_controlled"),
        "suite_role": suite.get("suite_role", "final_blind_acceptance"),
        "exposure_status": suite.get("exposure_status", "unsealed_one_shot_phase3d"),
        "distance_convention": dist_conv,
        "vehicle_limit_policy": veh_pol,
        "reference_kind": instances[0].get("reference_kind") if instances else "solver_reference",
        "comparison_mode": "local_recomputed",
        "budget_id": budget_id,
        "budget_ms": time_budget_ms,
        "n_instances": len(instances),
        "common_completed_count": len(strict_common_ids),
        "common_completed_algorithms": list(algorithm_ids),
        "strict_all_common_completed_count": len(strict_common_ids),
        "algorithms": alg_summaries,
    }

    anytime_agg: dict[str, Any] = {}
    if capture_anytime:
        checkpoints = ("10", "25", "100", "250", "500")
        for aid, bucket in anytime_raw.items():
            curves = bucket["curves"]
            if not curves:
                continue
            curve_means = {}
            for cp in checkpoints:
                vals = [float(c[cp]) for c in curves if isinstance(c.get(cp), (int, float))]
                curve_means[cp] = round(sum(vals) / len(vals), 4) if len(vals) == len(instances) else None
            ff = bucket["first_feasible_ms"]
            anytime_agg[aid] = {
                "curve_count": len(curves),
                "first_feasible_ms_mean": round(sum(ff) / len(ff), 4) if ff else None,
                "anytime_curve_means": curve_means,
            }

    return records, suite_summary, feature_rows, public_routes, anytime_agg


def _run_per_seed_family(
    *,
    frows: Sequence[Mapping[str, Any]],
    comparisons: Sequence[tuple[str, str, str]],
) -> dict[str, Any]:
    """Run paired comparisons over 120 blind instances per seed with Holm-Bonferroni correction."""
    entries: dict[str, dict[str, Any]] = {}
    keys_order: list[str] = []
    raw_ps: list[float] = []

    for label, cand_id, base_id in comparisons:
        cand_costs = [float(r["penalized_costs"][cand_id]) for r in frows]
        base_costs = [float(r["penalized_costs"][base_id]) for r in frows]
        res = paired_bootstrap_comparison(cand_costs, base_costs, n_boot=10000, seed=20261124)
        res["candidate_id"] = cand_id
        res["baseline_id"] = base_id
        entries[label] = res
        keys_order.append(label)
        raw_ps.append(float(res["wilcoxon_signed_rank"]["p_two_sided"]))

    holm_ps = holm_bonferroni_adjust(raw_ps)
    for k, p_adj in zip(keys_order, holm_ps):
        entries[k]["p_holm_wilcoxon"] = p_adj
        entries[k]["significant_holm_0_05"] = bool(p_adj < 0.05)
    return entries


def _enrich_dual_denominators(analysis: dict[str, Any]) -> dict[str, Any]:
    sbs_tot = float(analysis["global_sbs_total"])
    vbs_tot = float(analysis["global_vbs_total"])
    analysis["global_sbs_gap_over_sbs_pct"] = round(100.0 * (sbs_tot - vbs_tot) / max(sbs_tot, 1e-12), 4)
    analysis["global_sbs_gap_over_vbs_pct"] = round(100.0 * (sbs_tot - vbs_tot) / max(vbs_tot, 1e-12), 4)
    return analysis


def execute_m3_blind_evaluation(
    out_dir: Path,
    *,
    repo_root: Path = _REPO,
    sealed_path: Path,
    protocol_sha256: str,
    commitment_path: Path = M3_BLIND_COMMITMENT_PATH,
) -> dict[str, Any]:
    """Execute Phase 3D pre-blind freeze check, one-shot blind-120 unsealing, external suites, and Direction-2."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sealed_path = require_external_custody_path(sealed_path, repo_root)

    proto_bytes = (out_dir / "pre_blind_protocol_m3.json").read_bytes()
    if _sha256_bytes(proto_bytes) != protocol_sha256:
        raise ValueError("m3_pre_blind_protocol_hash_mismatch")
    protocol = json.loads(proto_bytes)
    commitment_sha256 = protocol["blind_commitment"]["commitment_file_sha256"]
    commitment = read_public_blind_commitment(
        commitment_path,
        expected_sha256=commitment_sha256,
        expected_suite_id=SEALED_M3_BLIND_SUITE_ID,
    )

    frozen_solvers = load_phase3c_frozen_roster(repo_root)
    frozen_by_id = {fs.solver_id: fs for fs in frozen_solvers}
    expected_roster = {row["solver_id"]: row["frozen_solver_sha256"] for row in protocol["frozen_solvers"]}
    actual_roster = {fs.solver_id: _sha256_bytes(canonical_json(fs.to_dict()).encode("utf-8")) for fs in frozen_solvers}
    if expected_roster != actual_roster:
        raise ValueError("m3_pre_blind_roster_hash_mismatch")
    for row in protocol["reference_baselines"]:
        if SOLVER_CATALOG[row["algorithm_id"]].code_sha256 != row["code_sha256"]:
            raise ValueError("m3_pre_blind_reference_hash_mismatch")

    report_path = out_dir / "blind_120_evaluation_report.json"
    if report_path.is_file() or (out_dir / "blind_evaluation.started").exists():
        raise FileExistsError("m3_blind_evaluation_output_already_used")

    attempt_marker = sealed_path.parent / f".{commitment['suite_content_sha256']}.blind-attempt"
    with attempt_marker.open("x", encoding="utf-8") as handle:
        handle.write(protocol_sha256 + "\n")
    with (out_dir / "blind_evaluation.started").open("x", encoding="utf-8") as handle:
        handle.write(protocol_sha256 + "\n")

    # 1. One-shot unseal & cryptographic verification of cvrp_m3_blind_120
    blind_suite, verification = unseal_and_verify_m3_blind_suite(
        sealed_path=sealed_path,
        commitment_path=commitment_path,
        expected_commitment_sha256=commitment_sha256,
    )
    dev24_suite = load_profile_suite(BENCHMARK_ID, "cvrp_dev_hetero_24", split="dev_train")
    sel64_suite = load_profile_suite(BENCHMARK_ID, "cvrp_select_multiscale_64", split="selection")
    fa120_suite = load_profile_suite(BENCHMARK_ID, "cvrp_final_accept_120", split="heldout")
    ext_eohs_suite = load_profile_suite(BENCHMARK_ID, "cvrp_ext_eohs_256", split="heldout")
    ext_abp_suite = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_abp_74", split="heldout")
    ext_x_suite = load_profile_suite(BENCHMARK_ID, "cvrp_ext_cvrplib_x_100", split="heldout")

    full_500_ids = [*REFERENCE_BASELINE_IDS, *[fs.solver_id for fs in frozen_solvers]]
    tight_ids = list(protocol["tight_25ms_blind_roster_ids"])
    ext_ids = list(protocol["external_benchmark_roster_ids"])

    # 2. Evaluate 500ms roster on dev_24, select_64, final_accept_120, and blind_120
    recs_dev24, sum_dev24, _, routes_dev24, _ = _evaluate_suite_algorithms(
        dev24_suite, algorithm_ids=full_500_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )
    recs_sel64, sum_sel64, frows_sel64, routes_sel64, _ = _evaluate_suite_algorithms(
        sel64_suite, algorithm_ids=full_500_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )
    recs_fa120, sum_fa120, frows_fa120, routes_fa120, _ = _evaluate_suite_algorithms(
        fa120_suite, algorithm_ids=full_500_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )
    recs_bl120_500, sum_bl120_500, frows_bl120_500, _, anytime_bl120 = _evaluate_suite_algorithms(
        blind_suite, algorithm_ids=full_500_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0, capture_anytime=True
    )

    # 3. Evaluate tight_25ms roster on blind_120
    recs_bl120_25, sum_bl120_25, frows_bl120_25, _, _ = _evaluate_suite_algorithms(
        blind_suite, algorithm_ids=tight_ids, frozen_by_id=frozen_by_id, budget_id="tight_25ms", time_budget_ms=25.0
    )

    # 4. Evaluate external benchmarks (500ms): EoH-S 256, CVRPLib A/B/P 74, CVRPLib Set X 100
    recs_eohs, sum_eohs, _, routes_eohs, _ = _evaluate_suite_algorithms(
        ext_eohs_suite, algorithm_ids=ext_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )
    recs_abp, sum_abp, _, routes_abp, _ = _evaluate_suite_algorithms(
        ext_abp_suite, algorithm_ids=ext_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )
    recs_x, sum_x, _, routes_x, _ = _evaluate_suite_algorithms(
        ext_x_suite, algorithm_ids=ext_ids, frozen_by_id=frozen_by_id, budget_id="standard_500ms", time_budget_ms=500.0
    )

    # 5. Per-seed statistical inference on blind_120 (500ms & 25ms) with Holm-Bonferroni correction
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
    hyp_500 = _run_per_seed_family(frows=frows_bl120_500, comparisons=comp_500_specs)

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
    hyp_25 = _run_per_seed_family(frows=frows_bl120_25, comparisons=comp_25_specs)

    # 6. Per-arm multi-seed aggregate tables (preserving individual seed values honestly alongside mean/std)
    def _arm_table(suite_sum: Mapping[str, Any], budget_tag: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for arm in PHASE3C_ARMS:
            seed_vals = []
            seed_rows: dict[str, Any] = {}
            for s in PHASE3C_SEEDS:
                sid = f"m3_3c_{budget_tag}_{arm}_s{s}"
                ov = suite_sum["algorithms"][sid]["overall"]
                seed_vals.append(float(ov["mean_tour_length"]))
                seed_rows[str(s)] = {
                    "solver_id": sid,
                    "mean_tour_length": ov["mean_tour_length"],
                    "completion_rate": ov["completion_rate"],
                    "ok_budget_exhausted_count": ov["ok_budget_exhausted_count"],
                    "solve_ms_p50": ov["solve_ms_p50"],
                    "solve_ms_p95": ov["solve_ms_p95"],
                }
            arr = np.asarray(seed_vals, dtype=np.float64)
            out[arm] = {
                "per_seed": seed_rows,
                "mean_across_seeds": round(float(arr.mean()), 4),
                "std_across_seeds": round(float(arr.std(ddof=1)), 4) if len(arr) > 1 else 0.0,
                "best_seed_mean": round(float(arr.min()), 4),
            }
        return out

    arm_bl120_500 = _arm_table(sum_bl120_500, "standard_500ms")
    arm_bl120_25 = _arm_table(sum_bl120_25, "tight_25ms")

    # 7. Section 5.3 Backbone & Anytime trajectory report on unsealed blind_120
    backbone_solvers = (
        "cw_parallel_merge",
        "cw_relocate_2opt",
        "m3_l3_ctrl_500ms",
        M3_EXTRA_L3_SOLVER_ID,
        "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125",
        "m3_3c_standard_500ms_arm_m3_2_fixed_l2a_s20261126",
    )
    backbone_blind120 = {
        "schema_version": "m3-backbone-blind120-attribution/v1",
        "suite_id": SEALED_M3_BLIND_SUITE_ID,
        "budget_ms": 500.0,
        "solvers": {
            sid: {
                "overall": sum_bl120_500["algorithms"][sid]["overall"],
                "anytime": anytime_bl120.get(sid),
            }
            for sid in backbone_solvers
        },
        "paired_tests": {
            k: hyp_500[k]
            for k in (
                "backbone__r2_l3_evolved_vs_l3_ctrl_500ms",
                "backbone__m3_3_s20261125_vs_l3_ctrl_500ms",
                "backbone__m3_3_s20261125_vs_m2_champ_s20261123",
            )
        },
    }

    # 8. Direction-2 Cross-Paradigm Selection (OOF on select_64 -> zero-shot frozen transfer to m3_blind_120 & final_accept_120)
    portfolios_cfg = protocol["direction2_selection_protocol"]["portfolios"]
    d2_analyses: dict[str, Any] = {}
    for pid, pspec in portfolios_cfg.items():
        members = pspec["members"]
        d2_analyses[f"select_64__{pid}"] = _enrich_dual_denominators(
            evaluate_oof_portfolio(
                "cvrp_select_multiscale_64",
                pid,
                frows_sel64,
                members,
                protocols=("cv12", "loro48", "loso3"),
            )
        )
        d2_analyses[f"m3_blind_120__{pid}_frozen"] = _enrich_dual_denominators(
            evaluate_frozen_transfer_portfolio(
                train_suite_id="cvrp_select_multiscale_64",
                test_suite_id=SEALED_M3_BLIND_SUITE_ID,
                portfolio_id=f"{pid}_frozen_m3_blind120",
                train_rows=frows_sel64,
                test_rows=frows_bl120_500,
                members=members,
            )
        )
        d2_analyses[f"final_accept_120__{pid}_frozen"] = _enrich_dual_denominators(
            evaluate_frozen_transfer_portfolio(
                train_suite_id="cvrp_select_multiscale_64",
                test_suite_id="cvrp_final_accept_120",
                portfolio_id=f"{pid}_frozen_final120",
                train_rows=frows_sel64,
                test_rows=frows_fa120,
                members=members,
            )
        )

    d2_overview: dict[str, Any] = {}
    for key, analysis in d2_analyses.items():
        proto_key = "frozen_transfer" if "frozen_transfer" in analysis["protocols"] else "cv12"
        sels = analysis["protocols"][proto_key]["selectors"]
        best_learned = min(
            (s for sname, s in sels.items() if sname not in {"oracle_vbs", "fixed_best_sbs"}),
            key=lambda s: float(s["total"]),
        )
        d2_overview[key] = {
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
        "schema_version": "m3-phase3d-blind120-evaluation-report/v1",
        "generated_at": _utc_now(),
        "pre_blind_protocol_sha256": hashlib.sha256(proto_bytes).hexdigest(),
        "commitment_verification": verification,
        "blind_120_standard_500ms_arm_summary": arm_bl120_500,
        "blind_120_tight_25ms_arm_summary": arm_bl120_25,
        "hypothesis_tests_blind_120_500ms": hyp_500,
        "hypothesis_tests_blind_120_25ms": hyp_25,
        "direction2_overview": d2_overview,
        "suite_summaries_500ms": {
            "cvrp_dev_hetero_24": sum_dev24,
            "cvrp_select_multiscale_64": sum_sel64,
            "cvrp_final_accept_120": sum_fa120,
            SEALED_M3_BLIND_SUITE_ID: sum_bl120_500,
        },
        "suite_summaries_25ms": {
            SEALED_M3_BLIND_SUITE_ID: sum_bl120_25,
        },
    }
    external_report = {
        "schema_version": "m3-phase3d-external-benchmarks-report/v1",
        "generated_at": blind_report["generated_at"],
        "pre_blind_protocol_sha256": blind_report["pre_blind_protocol_sha256"],
        "budget_id": "standard_500ms",
        "budget_ms": 500.0,
        "suites": {
            "cvrp_ext_eohs_256": sum_eohs,
            "cvrp_ext_cvrplib_abp_74": sum_abp,
            "cvrp_ext_cvrplib_x_100": sum_x,
        },
    }

    report_path.write_text(json.dumps(blind_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "external_benchmarks_report.json").write_text(
        json.dumps(external_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out_dir / "backbone_blind120_report.json").write_text(
        json.dumps(backbone_blind120, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out_dir / "direction2_cross_paradigm_report.json").write_text(
        json.dumps(
            {
                "schema_version": "m3-phase3d-direction2-report/v1",
                "generated_at": blind_report["generated_at"],
                "pre_blind_protocol_sha256": blind_report["pre_blind_protocol_sha256"],
                "overview": d2_overview,
                "analyses": d2_analyses,
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
        "external_report": external_report,
        "backbone_blind120": backbone_blind120,
        "direction2_analyses": d2_analyses,
        "records_500ms": {
            "cvrp_dev_hetero_24": recs_dev24,
            "cvrp_select_multiscale_64": recs_sel64,
            "cvrp_final_accept_120": recs_fa120,
            SEALED_M3_BLIND_SUITE_ID: recs_bl120_500,
            "cvrp_ext_eohs_256": recs_eohs,
            "cvrp_ext_cvrplib_abp_74": recs_abp,
            "cvrp_ext_cvrplib_x_100": recs_x,
        },
        "records_25ms": {
            SEALED_M3_BLIND_SUITE_ID: recs_bl120_25,
        },
        "public_routes_500ms": {
            "cvrp_dev_hetero_24": routes_dev24,
            "cvrp_select_multiscale_64": routes_sel64,
            "cvrp_final_accept_120": routes_fa120,
            "cvrp_ext_eohs_256": routes_eohs,
            "cvrp_ext_cvrplib_abp_74": routes_abp,
            "cvrp_ext_cvrplib_x_100": routes_x,
        },
        "feature_rows_blind120_500": frows_bl120_500,
        "frozen_solvers": frozen_solvers,
    }
