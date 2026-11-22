"""Generate controlled same-stream OBP protocol ablation & SHA-256 frozen roster manifest,
and sync T1 O(n^4) metadata into build/workbench_m15_bundle/algorithms.json.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.benchmark.catalog import load_profile_suite
from agent_skill_loop.cvrp_workbench.solvers import MILESTONE15_CVRP_IDS, SOLVER_CATALOG
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.cvrp_workbench.tsp_obp import (
    OBP_SOLVER_CATALOG,
    TSP_SOLVER_CATALOG,
    _compile_obp_rule,
    _run_obp_fast,
)
from agent_skill_loop.problems import bp_island605

OUT_DIR = REPO / "experiments" / "milestone15"
BUNDLE_DIR = REPO / "build" / "workbench_m15_bundle"


def _eval_allow_new_bin(fn, instances: list[dict[str, Any]], *, ratio_of_means: bool) -> dict[str, Any]:
    used_list, gaps = [], []
    for inst in instances:
        cap = int(inst["capacity"])
        items = inst["items"]
        bins = np.full(len(items), cap, dtype=np.int64)
        for item in items:
            valid = np.nonzero((bins - item) >= 0)[0]
            with np.errstate(all="ignore"):
                scores = np.asarray(fn(item, bins[valid]), dtype=float)
            if not np.all(np.isfinite(scores)):
                scores = np.nan_to_num(scores, nan=-1e30, posinf=1e30, neginf=-1e30)
            best = int(valid[int(np.argmax(scores))])
            bins[best] -= item
        used = int(np.count_nonzero(bins != cap))
        ref = float(inst["reference_objective"])
        used_list.append(used)
        gaps.append((used - ref) / ref)
    if ratio_of_means:
        mean_l1 = float(instances[0]["dataset_mean_l1"])
        return {
            "ratio_of_means_excess": round(float((np.mean(used_list) - mean_l1) / mean_l1), 6),
            "mean_rel_gap": round(float(np.mean(gaps)), 6),
            "bins_used": used_list,
        }
    return {
        "mean_rel_gap": round(float(np.mean(gaps)), 6),
        "mean_bins_used": round(float(np.mean(used_list)), 4),
    }


def _eval_open_only(alg_id: str, fn, instances: list[dict[str, Any]], *, ratio_of_means: bool) -> dict[str, Any]:
    used_list, gaps = [], []
    for inst in instances:
        loads, _, _ = _run_obp_fast(alg_id, fn, inst["items"], float(inst["capacity"]), time_budget_ms=5000.0)
        used = len(loads)
        ref = float(inst["reference_objective"])
        used_list.append(used)
        gaps.append((used - ref) / ref)
    if ratio_of_means:
        mean_l1 = float(instances[0]["dataset_mean_l1"])
        return {
            "ratio_of_means_excess": round(float((np.mean(used_list) - mean_l1) / mean_l1), 6),
            "mean_rel_gap": round(float(np.mean(gaps)), 6),
            "bins_used": used_list,
        }
    return {
        "mean_rel_gap": round(float(np.mean(gaps)), 6),
        "mean_bins_used": round(float(np.mean(used_list)), 4),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO), text=True).strip()

    # 1. Controlled same-stream OBP protocol ablation (isolating bin-opening rule only)
    leg5 = bp_island605.build_suite()["instances"]
    bpplib = load_profile_suite(BENCHMARK_ID, "obp_ext_bpplib", split="heldout")["instances"]
    obp_ids = [
        "obp_best_fit",
        "i605_obp_b1_exp_deadzone",
        "i605_obp_b16_log_half",
        "i605_obp_b50_sqrt_tier",
        "i605_obp_b117_hardcap_anti",
    ]
    weibull5_rows = {}
    bpplib_rows = {}
    for aid in obp_ids:
        spec = OBP_SOLVER_CATALOG[aid]
        fn = _compile_obp_rule(spec.code_source, aid)
        fn_open = None if aid == "obp_best_fit" else fn
        a_w = _eval_allow_new_bin(fn, leg5, ratio_of_means=True)
        o_w = _eval_open_only(aid, fn_open, leg5, ratio_of_means=True)
        weibull5_rows[aid] = {
            "allow_open_new_bin": a_w,
            "open_bins_only": o_w,
            "delta_open_minus_allow": round(o_w["ratio_of_means_excess"] - a_w["ratio_of_means_excess"], 6),
        }
        a_b = _eval_allow_new_bin(fn, bpplib, ratio_of_means=False)
        o_b = _eval_open_only(aid, fn_open, bpplib, ratio_of_means=False)
        bpplib_rows[aid] = {
            "allow_open_new_bin": a_b,
            "open_bins_only": o_b,
            "delta_open_minus_allow": round(o_b["mean_rel_gap"] - a_b["mean_rel_gap"], 6),
        }

    ablation_payload = {
        "schema_version": "milestone15-obp-protocol-ablation/v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "design": (
            "Strictly controlled same-stream ablation toggling ONLY the bin-opening protocol "
            "(allow_open_new_bin from bp_island605.py vs open_bins_only from tsp_obp.py) on identical item streams."
        ),
        "island605_weibull_5x5000_c100": weibull5_rows,
        "bpplib_70_multi_capacity": bpplib_rows,
    }
    ablation_path = OUT_DIR / "obp_protocol_ablation.json"
    ablation_path.write_text(json.dumps(ablation_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 2. Explicit SHA-256 Frozen Roster Manifest (all 15 Milestone 1.5 additions)
    tsp_m15_ids = ("i605_tsp_t1_rollout", "i605_tsp_t46_farness", "i605_tsp_t69_dest_regret", "i605_tsp_t81_norm_smooth")
    obp_m15_ids = ("i605_obp_b1_exp_deadzone", "i605_obp_b50_sqrt_tier", "i605_obp_b16_log_half", "i605_obp_b117_hardcap_anti")
    roster_entries = []
    for aid in MILESTONE15_CVRP_IDS:
        s = SOLVER_CATALOG[aid]
        roster_entries.append({
            "algorithm_id": aid,
            "problem_family": "cvrp",
            "display_name": s.display_name,
            "paradigm": s.paradigm,
            "kb_entry_id": s.kb_entry_id,
            "code_path": s.code_path,
            "code_sha256": s.code_sha256,
            "selection_basis": "Screened strictly on cvrp_dev_hetero_24 (24+4) + cvrp_select_multiscale_64 (64) = 92 instances with zero access to cvrp_final_accept_120.",
        })
    for aid in tsp_m15_ids:
        s = TSP_SOLVER_CATALOG[aid]
        roster_entries.append({
            "algorithm_id": aid,
            "problem_family": "tsp",
            "display_name": s.display_name,
            "paradigm": s.paradigm,
            "kb_entry_id": s.kb_entry_id,
            "code_path": s.code_path,
            "code_sha256": s.code_sha256,
            "selection_basis": "Screened on tsp_ext_eohs_128 (flagged as selection_screening_suite); externally validated on tsp_ext_tsplib_euc2d (18 OPT).",
        })
    for aid in obp_m15_ids:
        s = OBP_SOLVER_CATALOG[aid]
        roster_entries.append({
            "algorithm_id": aid,
            "problem_family": "obp",
            "display_name": s.display_name,
            "paradigm": s.paradigm,
            "kb_entry_id": s.kb_entry_id,
            "code_path": s.code_path,
            "code_sha256": s.code_sha256,
            "selection_basis": "Screened on 7-instance multi-capacity + 10x scaling slice under workbench open_bins_only protocol; controlled same-stream ablation recorded in obp_protocol_ablation.json.",
        })

    roster_payload = {
        "schema_version": "milestone15-frozen-roster-manifest/v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_git_head": head_sha,
        "provenance_note": (
            "Records exact code_sha256 for all 15 Milestone 1.5 solvers added on top of Milestone 1 (30 -> 45). "
            "Note: created retrospectively during post-audit hardening after initial M1.5 bundle run; "
            "screening script tools/reproduce_milestone15.py never loads cvrp_final_accept_120. "
            "knowledge_store manifest.json:source_main_sha (d6433549) reflects the historical KB inventory snapshot baseline."
        ),
        "screening_artifact_sha256": hashlib.sha256((OUT_DIR / "workbench_screening_605.json").read_bytes()).hexdigest(),
        "legacy_artifact_sha256": hashlib.sha256((OUT_DIR / "legacy_reproduction_605.json").read_bytes()).hexdigest(),
        "obp_ablation_sha256": hashlib.sha256(ablation_path.read_bytes()).hexdigest(),
        "solver_count": len(roster_entries),
        "solvers": roster_entries,
    }
    roster_path = OUT_DIR / "frozen_roster_manifest.json"
    roster_path.write_text(json.dumps(roster_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3. Sync T1 O(n^4) metadata into build/workbench_m15_bundle/algorithms.json & workbench_manifest.json
    alg_json_p = BUNDLE_DIR / "algorithms.json"
    if alg_json_p.is_file():
        alg_doc = json.loads(alg_json_p.read_text(encoding="utf-8"))
        t1_spec = TSP_SOLVER_CATALOG["i605_tsp_t1_rollout"]
        for row in alg_doc["algorithms"]:
            if row["algorithm_id"] == "i605_tsp_t1_rollout":
                row["display_name"] = t1_spec.display_name
                row["description"] = t1_spec.description
        alg_json_p.write_text(json.dumps(alg_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

        # Refresh workbench_manifest.json hashes cleanly
        wb_m_p = BUNDLE_DIR / "workbench_manifest.json"
        wb_m = json.loads(wb_m_p.read_text(encoding="utf-8"))
        bundle_files = []
        for path in sorted(p for p in BUNDLE_DIR.rglob("*") if p.is_file() and p.name != "workbench_manifest.json"):
            bundle_files.append({
                "path": path.relative_to(BUNDLE_DIR).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            })
        wb_m["files"] = bundle_files
        wb_m["base_git_head"] = head_sha
        wb_m["frozen_roster_sha256"] = hashlib.sha256(roster_path.read_bytes()).hexdigest()
        wb_m_p.write_text(json.dumps(wb_m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("Wrote:", ablation_path, roster_path, "and synced bundle algorithms.json + workbench_manifest.json")


if __name__ == "__main__":
    main()
