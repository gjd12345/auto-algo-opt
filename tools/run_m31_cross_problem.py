"""Milestone 3.1 Cross-Problem Generalization Runner (TSP, Online OBP, and Independent Offline BPP).

Orchestrates:
  1. baseline-check : Unified Session runtime baseline freeze + fresh-worker case-by-case re-eval
  2. seal-blind     : External custody sealing for tsp_m31_blind_72, obp_m31_blind_72, bpp_m31_blind_72
  3. emit-mux       : Emit tools/multi_task_mux.py concurrent pane manifest across seeds & lanes
  4. run-one        : Execute or crash-resume one (lane, seed) autonomous ResearchAgent run
  5. eval-select    : Evaluate winners + strong baselines on M3.1 selection suites + invariance gates
  6. unseal-blind   : One-shot atomic unseal & evaluation of blinded M3.1 suites (BPP strictly separated)
  7. eval-external  : Evaluate TSP finalists on TSPLIB 18 and Online OBP finalists on BPPLib 70
  8. report         : Compute per-problem stats (Paired Wilcoxon + 10k bootstrap + Holm-Bonferroni),
                      regime slices, added code volume per problem, and strict BPP separation tables
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.m31_suites import M31_PROTOCOL_IDS, m31_suite_id
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.cvrp_workbench.tsp_obp import (
    evaluate_obp_algorithm_on_instance,
    evaluate_tsp_algorithm_on_instance,
)
from agent_skill_loop.interface_design.blind_eval import (
    paired_bootstrap_comparison,
    paired_wilcoxon_signed_rank,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import (
    MANIFESTS_DIR,
    _M31_CUSTODY_NAME,
    seal_m31_blind_suite,
    unseal_and_evaluate_m31,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.dynamic_eoh import derive_effective_batch_timeout_s
from agent_skill_loop.interface_design.planner import build_design_for_template
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import (
    freeze_session_baseline,
    load_dev_or_public_suite,
    re_eval_session_baseline,
)
from agent_skill_loop.interface_design.validator import InterfaceValidator
from agent_skill_loop.problems.bpp_offline import bpp_bfd, bpp_ffd, verify_bpp_solution
from agent_skill_loop.session_runtime import initialize_session
from research_agent.contracts import AgentConfig, atomic_write_json, utc_now
from research_agent.loop import run_research_agent

DEFAULT_SEEDS: tuple[int, ...] = (20261124, 20261125, 20261126)
DEFAULT_LANES: tuple[str, ...] = ("tsp_l1", "tsp_l2", "obp_online", "bpp_offline")

LANE_SPECS: dict[str, dict[str, Any]] = {
    "tsp_l1": {
        "problem_family": "tsp",
        "protocol_id": "tsp/v1",
        "dev_suite_id": "tsp_m31_dev_36",
        "select_suite_id": "tsp_m31_select_36",
        "blind_suite_id": "tsp_m31_blind_72",
        "allowed_templates": ("tsp_constructive_step",),
        "initial_template_id": "tsp_constructive_step",
        "strong_baseline": "tsp_nn_2opt",
        "secondary_baselines": ("tsp_nn", "tsp_farthest_insertion"),
    },
    "tsp_l2": {
        "problem_family": "tsp",
        "protocol_id": "tsp/v1",
        "dev_suite_id": "tsp_m31_dev_36",
        "select_suite_id": "tsp_m31_select_36",
        "blind_suite_id": "tsp_m31_blind_72",
        "allowed_templates": ("tsp_guided_insertion_2opt",),
        "initial_template_id": "tsp_guided_insertion_2opt",
        "strong_baseline": "tsp_nn_2opt",
        "secondary_baselines": ("tsp_nn", "tsp_farthest_insertion"),
    },
    "obp_online": {
        "problem_family": "obp",
        "protocol_id": "obp_online/v1",
        "dev_suite_id": "obp_m31_dev_36",
        "select_suite_id": "obp_m31_select_36",
        "blind_suite_id": "obp_m31_blind_72",
        "allowed_templates": ("obp_online_priority",),
        "initial_template_id": "obp_online_priority",
        "strong_baseline": "obp_best_fit",
        "secondary_baselines": ("obp_first_fit",),
    },
    "bpp_offline": {
        "problem_family": "bpp",
        "protocol_id": "bpp_offline/v1",
        "dev_suite_id": "bpp_m31_dev_36",
        "select_suite_id": "bpp_m31_select_36",
        "blind_suite_id": "bpp_m31_blind_72",
        "allowed_templates": ("bpp_offline_reorder_repack",),
        "initial_template_id": "bpp_offline_reorder_repack",
        "strong_baseline": "bpp_ffd",
        "secondary_baselines": ("bpp_bfd",),
    },
}

ADDED_CODE_PATHS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "tsp": (
        "agent_skill_loop/interface_design/tsp_adapter.py",
        "agent_skill_loop/interface_design/tsp_templates.py",
        "agent_skill_loop/interface_design/tsp_probes.py",
    ),
    "obp": (
        "agent_skill_loop/interface_design/packing_adapters.py",
        "agent_skill_loop/interface_design/obp_templates.py",
        "agent_skill_loop/interface_design/packing_probes.py",
    ),
    "bpp": (
        "agent_skill_loop/problems/bpp_offline.py",
        "agent_skill_loop/interface_design/packing_adapters.py",
        "agent_skill_loop/interface_design/bpp_templates.py",
        "agent_skill_loop/interface_design/packing_probes.py",
    ),
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_obj(rec: Mapping[str, Any]) -> float | None:
    if not (rec.get("valid") is True or rec.get("feasible") is True):
        return None
    for k in ("objective", "tour_length", "bins_used"):
        v = rec.get(k)
        if v is not None and not isinstance(v, bool) and isinstance(v, (int, float)):
            return float(v)
    return None


def _eval_baseline_on_instance(
    alg_id: str,
    family: str,
    instance: Mapping[str, Any],
    *,
    distance_convention: str,
    time_budget_ms: float = 500.0,
) -> dict[str, Any]:
    if family == "tsp":
        return evaluate_tsp_algorithm_on_instance(
            alg_id,
            instance,
            distance_convention=distance_convention,
            time_budget_ms=time_budget_ms,
        )
    if family == "obp":
        return evaluate_obp_algorithm_on_instance(alg_id, instance, time_budget_ms=time_budget_ms)
    if family == "bpp":
        t0 = time.perf_counter()
        bins = bpp_bfd(instance["items"], instance["capacity"]) if alg_id == "bpp_bfd" else bpp_ffd(instance["items"], instance["capacity"])
        ver = verify_bpp_solution(instance, bins)
        return {
            "algorithm_id": alg_id,
            "problem_family": "bpp",
            "protocol_id": "bpp_offline/v1",
            "status": "ok" if ver.get("valid") else "infeasible",
            "valid": bool(ver.get("valid")),
            "completed": bool(ver.get("valid")),
            "bins_used": ver.get("bins_used"),
            "objective": ver.get("bins_used"),
            "reference_objective": instance.get("reference_objective"),
            "solve_ms": round((time.perf_counter() - t0) * 1000.0, 4),
            "verify_ms": ver.get("verify_ms"),
        }
    raise ValueError(f"unsupported_m31_family:{family}")


def _eval_solver_on_suite(
    solver_or_alg: FrozenInterfaceSolver | str,
    family: str,
    suite: Mapping[str, Any],
    *,
    time_budget_ms: float = 500.0,
) -> dict[str, Any]:
    dist_conv = str(suite.get("distance_convention") or ("euc_2d_float" if family == "tsp" else "not_applicable"))
    veh_pol = str(suite.get("vehicle_limit_policy") or "not_applicable")
    outer_s = derive_effective_batch_timeout_s(1, time_budget_ms, floor_s=max(5.0, time_budget_ms / 1000.0 + 3.0))
    instances = list(suite["instances"])
    records: list[dict[str, Any]] = []
    penalized: list[float] = []
    valid_vals: list[float] = []
    solve_ms_vals: list[float] = []
    by_dist: dict[str, list[tuple[dict[str, Any], float]]] = {}
    by_size: dict[str, list[tuple[dict[str, Any], float]]] = {}
    by_stratum: dict[str, list[tuple[dict[str, Any], float]]] = {}

    for inst in instances:
        if isinstance(solver_or_alg, FrozenInterfaceSolver):
            rec = evaluate_frozen_interface_solver(
                solver_or_alg,
                inst,
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                solve_deadline_ms=time_budget_ms,
                outer_timeout_s=outer_s,
                protocol_id=suite.get("protocol_id") or M31_PROTOCOL_IDS[family],
            )
        else:
            rec = _eval_baseline_on_instance(
                str(solver_or_alg),
                family,
                inst,
                distance_convention=dist_conv,
                time_budget_ms=time_budget_ms,
            )
        obj = _extract_obj(rec)
        rec_completed = bool(obj is not None and (rec.get("completed", True) if isinstance(solver_or_alg, FrozenInterfaceSolver) else rec.get("status") == "ok"))
        if rec_completed:
            valid_vals.append(obj)
            pen = obj
        else:
            ref = inst.get("reference_objective")
            pen = 2.0 * float(ref) if isinstance(ref, (int, float)) and float(ref) > 0 else 1e6
        penalized.append(pen)
        if rec.get("solve_ms") is not None:
            solve_ms_vals.append(float(rec["solve_ms"]))
        pub = {
            "instance_id": inst["instance_id"],
            "size": inst.get("size"),
            "distribution": inst.get("distribution"),
            "stratum": inst.get("stratum"),
            "cell": inst.get("cell"),
            "objective": obj if rec_completed else None,
            "feasible_incumbent_objective": obj,
            "penalized_objective": pen,
            "reference_objective": inst.get("reference_objective"),
            "valid": rec_completed,
            "feasible": obj is not None,
            "completed": rec_completed,
            "budget_exhausted": bool(rec.get("budget_exhausted", False)),
            "solve_ms": rec.get("solve_ms"),
        }
        records.append(pub)
        if inst.get("distribution") is not None:
            by_dist.setdefault(str(inst["distribution"]), []).append((pub, pen))
        if inst.get("size") is not None:
            by_size.setdefault(str(inst["size"]), []).append((pub, pen))
        if inst.get("stratum") is not None:
            by_stratum.setdefault(str(inst["stratum"]), []).append((pub, pen))

    def _agg_slice(bucket: Mapping[str, list[tuple[dict[str, Any], float]]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, items in sorted(bucket.items()):
            objs = [x[0]["objective"] for x in items if x[0]["objective"] is not None]
            pens = [x[1] for x in items]
            out[key] = {
                "count": len(items),
                "valid_count": len(objs),
                "completion_rate": round(len(objs) / max(1, len(items)), 6),
                "mean_objective": round(sum(objs) / len(objs), 6) if objs else None,
                "penalized_mean_objective": round(sum(pens) / max(1, len(pens)), 6),
            }
        return out

    n_tot = len(records)
    n_ok = len(valid_vals)
    return {
        "suite_id": suite.get("suite_id"),
        "protocol_id": suite.get("protocol_id") or M31_PROTOCOL_IDS[family],
        "instance_count": n_tot,
        "valid_count": n_ok,
        "completion_rate": round(n_ok / max(1, n_tot), 6),
        "all_completed": bool(n_tot > 0 and n_ok == n_tot),
        "budget_exhausted_count": sum(1 for r in records if r.get("budget_exhausted")),
        "valid_only_mean_objective": round(sum(valid_vals) / n_ok, 6) if valid_vals else None,
        "penalized_mean_objective": round(sum(penalized) / max(1, n_tot), 6),
        "solve_ms_mean": round(sum(solve_ms_vals) / len(solve_ms_vals), 4) if solve_ms_vals else None,
        "slices": {
            "by_size": _agg_slice(by_size),
            "by_distribution": _agg_slice(by_dist),
            "by_stratum": _agg_slice(by_stratum),
        },
        "records": records,
    }


def _is_completed_record(rec: Mapping[str, Any]) -> bool:
    if "completed" in rec:
        return bool(rec.get("completed")) and bool(rec.get("feasible")) and rec.get("objective") is not None
    return bool(rec.get("feasible")) and rec.get("objective") is not None


def _pair_metrics(cand_recs: Sequence[Mapping[str, Any]], base_recs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cand_pens = [float(r["penalized_objective"]) for r in cand_recs]
    base_pens = [float(r["penalized_objective"]) for r in base_recs]
    w = paired_wilcoxon_signed_rank(cand_pens, base_pens)
    b = paired_bootstrap_comparison(cand_pens, base_pens, n_boot=10000, seed=20261124)
    common_cand: list[float] = []
    common_base: list[float] = []
    for c_r, b_r in zip(cand_recs, base_recs):
        if _is_completed_record(c_r) and _is_completed_record(b_r):
            common_cand.append(float(c_r["objective"]))
            common_base.append(float(b_r["objective"]))
    common_delta_pct = (
        round(100.0 * (sum(common_cand) - sum(common_base)) / max(sum(common_base), 1e-12), 4)
        if common_cand
        else None
    )
    overall_delta_pct = round(100.0 * (sum(cand_pens) - sum(base_pens)) / max(sum(base_pens), 1e-12), 4) if cand_pens else None
    return {
        "n_instances": len(cand_recs),
        "common_completed_count": len(common_cand),
        "overall_delta_pct_vs_baseline": overall_delta_pct,
        "common_completed_delta_pct_vs_baseline": common_delta_pct,
        "wilcoxon_p_two_sided": w["p_two_sided"],
        "bootstrap": b,
    }


def cmd_baseline_check(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    bl_root = out_dir / "baseline_sessions"
    results: dict[str, Any] = {}
    targets = [
        ("tsp", "tsp_m31_dev_36", "tsp_m31_dev_36", "tsp_constructive_step", "tsp/v1", "tsp_nn_2opt"),
        ("tsp_tsplib", "tsp_m31_dev_36", "tsp_ext_tsplib_euc2d", "tsp_constructive_step", "tsp/v1", "tsp_nn_2opt"),
        ("obp", "obp_m31_dev_36", "obp_m31_dev_36", "obp_online_priority", "obp_online/v1", "obp_best_fit"),
        ("bpp", "bpp_m31_dev_36", "bpp_m31_dev_36", "bpp_offline_reorder_repack", "bpp_offline/v1", "bpp_ffd"),
    ]
    for label, init_suite, eval_suite, tpl_id, expected_proto, strong_bl in targets:
        s_dir = bl_root / label
        if s_dir.exists():
            import shutil
            shutil.rmtree(s_dir)
        prob_family = "tsp" if label.startswith("tsp") else label
        init_res = initialize_session(
            output=s_dir,
            operation_id=f"init_{label}",
            problem=prob_family,
            benchmark_id=BENCHMARK_ID,
            benchmark_profile_name=init_suite,
            eoh_model="mock",
            eoh_endpoint="mock://local",
            max_rounds=1,
        )
        ver = int(init_res["state_version"])
        fr = freeze_session_baseline(
            run=s_dir,
            operation_id=f"freeze_{label}",
            expected_state_version=ver,
            baseline_id=f"bl_{label}",
            template_id=tpl_id,
            postprocess_mode="none",
            time_budget_ms=500.0,
            suite_id=eval_suite,
        )
        ver = int(fr["state_version"])
        re_ev = re_eval_session_baseline(
            run=s_dir,
            operation_id=f"reeval_{label}",
            expected_state_version=ver,
            baseline_id=f"bl_{label}",
            suite_id=eval_suite,
            protocol_id=expected_proto,
            time_budget_ms=500.0,
            replicate_id="rep_1",
        )
        suite_obj = load_dev_or_public_suite(
            eval_suite,
            split="heldout" if eval_suite == "tsp_ext_tsplib_euc2d" else "dev_train",
            role="diagnostic_interactive",
        )
        strong_eval = _eval_solver_on_suite(strong_bl, prob_family, suite_obj, time_budget_ms=500.0)
        fr_doc = json.loads((s_dir / fr["result"]["baseline_ref"]).read_text(encoding="utf-8"))
        re_doc = json.loads((s_dir / re_ev["result"]["report_ref"]).read_text(encoding="utf-8"))
        matched = bool(re_ev["result"]["matched_reference"])
        if not matched or not re_ev["result"]["all_completed"]:
            raise RuntimeError(f"baseline_check_failed:{label}")
        results[label] = {
            "suite_id": eval_suite,
            "protocol_id": expected_proto,
            "baseline_id": f"bl_{label}",
            "matched_reference": matched,
            "completion_rate": re_ev["result"]["completion_rate"],
            "mean_objective": re_ev["result"]["mean_objective"],
            "completion_bitmap_equal": (
                re_doc["evaluation"]["completion_bitmap"] == fr_doc["baseline_eval"]["completion_bitmap"]
            ),
            "strong_comparator": strong_bl,
            "strong_mean_objective": strong_eval["penalized_mean_objective"],
            "strong_completion_rate": strong_eval["completion_rate"],
        }
    report = {
        "schema_version": "m31-baseline-check/v1",
        "checked_at": utc_now(),
        "results": results,
    }
    atomic_write_json(out_dir / "baseline_check_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_seal_blind(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    custody_dir = Path(args.custody_dir).resolve()
    commitment_dir = Path(args.commitment_dir).resolve()
    commitment_dir.mkdir(parents=True, exist_ok=True)
    sealed: dict[str, Any] = {}
    for family in args.families:
        suite_id = m31_suite_id(family, "blind")
        cpath = commitment_dir / f"{suite_id}_commitment.json"
        if (custody_dir / f"{suite_id}_sealed.json").is_file() and cpath.is_file():
            com = json.loads(cpath.read_text(encoding="utf-8"))
            if com.get("commitment_status") == "sealed_external":
                sealed[family] = {
                    "suite_id": suite_id,
                    "commitment_path": str(cpath),
                    "commitment_sha256": _sha256_file(cpath),
                    "custody_dir": str(custody_dir),
                    "reused_existing": True,
                }
                continue
        res = seal_m31_blind_suite(family, commitment_path=cpath, custody_dir=custody_dir)
        sealed[family] = {
            "suite_id": res["suite_id"],
            "commitment_path": res["commitment_path"],
            "commitment_sha256": res["commitment_sha256"],
            "custody_dir": str(custody_dir),
            "reused_existing": False,
        }
    out_payload = {"schema_version": "m31-blind-seals/v1", "sealed": sealed}
    atomic_write_json(out_dir / "seal_summary.json", out_payload)
    print(json.dumps(out_payload, ensure_ascii=False, indent=2))
    return 0


def cmd_emit_mux(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    manifest_path = Path(args.manifest_path).resolve() if args.manifest_path else (out_dir / "mux_m31_manifest.json")
    panes: list[dict[str, Any]] = []
    for lane in args.lanes:
        for seed in args.seeds:
            pane_id = f"m31_{lane}_s{seed}"
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--output-dir", str(out_dir),
                "--time-budget-ms", str(args.time_budget_ms),
                "run-one",
                "--lane", str(lane),
                "--seed", str(seed),
                "--mode", str(args.mode),
                "--request-cap", str(args.request_cap),
                "--model", str(args.model),
                "--endpoint", str(args.endpoint),
                "--api-key-env", str(args.api_key_env),
                "--max-rounds", str(args.max_rounds),
                "--eoh-max-sample-nums", str(args.eoh_max_sample_nums),
            ]
            if args.resume:
                cmd.append("--resume")
            panes.append({"id": pane_id, "command": cmd, "cwd": str(REPO)})
    manifest = {"panes": panes}
    atomic_write_json(manifest_path, manifest)
    print(json.dumps({"manifest_path": str(manifest_path), "pane_count": len(panes)}, indent=2))
    return 0


def cmd_run_one(args: argparse.Namespace) -> int:
    load_local_env()
    spec = LANE_SPECS[args.lane]
    out_dir = Path(args.output_dir).resolve()
    run_dir = out_dir / "runs" / f"{args.lane}_s{args.seed}"
    ckpt_file = run_dir / "agent_checkpoint.json"
    resume = bool(args.resume and ckpt_file.is_file())
    dev_suite = load_dev_or_public_suite(str(spec["dev_suite_id"]), split="dev_train", role="diagnostic_interactive")
    dev_count = len(dev_suite["instances"])
    cfg = AgentConfig(
        run_id=f"m31_{args.lane}_s{args.seed}",
        output_dir=str(run_dir),
        problem_family=spec["problem_family"],
        arm_id=f"m31_{args.lane}",
        max_rounds=int(args.max_rounds),
        total_request_cap=int(args.request_cap),
        eoh_pop_size=2,
        eoh_n_pop=2,
        eoh_max_sample_nums=int(args.eoh_max_sample_nums),
        dev_instance_count=dev_count,
        instance_time_budget_ms=float(args.time_budget_ms),
        allowed_templates=tuple(spec["allowed_templates"]),
        allowed_postprocess_modes=("none",),
        initial_template_id=str(spec["initial_template_id"]),
        initial_postprocess_mode="none",
        planner_model=str(args.model),
        eoh_model=str(args.model),
        endpoint=str(args.endpoint),
        api_key_env=str(args.api_key_env),
        search_seed=int(args.seed),
        dev_suite_id=str(spec["dev_suite_id"]),
        dev_split="dev_train",
        use_benchmark_dev_suite=True,
        checkpoint_budgets=(int(args.request_cap),),
        mode=str(args.mode),
        request_timeout_s=float(args.request_timeout_s),
        wall_seconds=float(args.wall_seconds),
    )
    try:
        summary = run_research_agent(cfg, resume=resume)
    except ProviderFailure as exc:
        status_payload = {
            "run_id": cfg.run_id,
            "lane": args.lane,
            "seed": args.seed,
            "status": "resumable",
            "reason": str(exc),
            "checkpoint_preserved": ckpt_file.is_file(),
            "exit_code": 75,
            "updated_at": utc_now(),
        }
        if run_dir.is_dir():
            atomic_write_json(run_dir / "run_interrupt_status.json", status_payload)
        print(json.dumps(status_payload, ensure_ascii=False, indent=2))
        return 75
    atomic_write_json(
        run_dir / "run_interrupt_status.json",
        {"run_id": cfg.run_id, "status": summary.get("final_phase"), "checkpoint_preserved": ckpt_file.is_file(), "updated_at": utc_now()},
    )
    print(json.dumps({
        "run_id": cfg.run_id,
        "lane": args.lane,
        "seed": args.seed,
        "final_phase": summary.get("final_phase"),
        "best_dev_objective": summary.get("best_dev_objective"),
        "best_solver_manifest_ref": summary.get("best_solver_manifest_ref"),
        "requests_used": (summary.get("budget_summary") or {}).get("attempted_requests"),
    }, ensure_ascii=False, indent=2))
    return 0


def _discover_run_solvers_with_exclusions(
    out_dir: Path, lanes: Sequence[str],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_lane: dict[str, list[dict[str, Any]]] = {lane: [] for lane in lanes}
    excluded_runs: list[dict[str, Any]] = []
    runs_dir = out_dir / "runs"
    if not runs_dir.is_dir():
        return by_lane, excluded_runs
    for run_path in sorted(runs_dir.iterdir()):
        if not run_path.is_dir():
            continue
        summ_path = run_path / "research_summary.json"
        if not summ_path.is_file():
            lane_guess = next((l for l in lanes if run_path.name.startswith(f"{l}_s")), None)
            if lane_guess is not None:
                excluded_runs.append({
                    "run_dir": str(run_path),
                    "lane": lane_guess,
                    "run_id": f"m31_{run_path.name}",
                    "final_phase": None,
                    "best_dev_objective": None,
                    "reason": "missing_summary",
                })
            continue
        summ = json.loads(summ_path.read_text(encoding="utf-8"))
        lane = next((l for l in lanes if summ.get("arm_id") == f"m31_{l}" or run_path.name.startswith(f"{l}_s")), None)
        if lane is None:
            continue
        best_ref = summ.get("best_solver_manifest_ref")
        best_dev = summ.get("best_dev_objective")
        final_phase = summ.get("final_phase")
        if not best_ref or best_dev is None or not (run_path / best_ref).is_file():
            excluded_runs.append({
                "run_dir": str(run_path),
                "lane": lane,
                "run_id": summ.get("run_id"),
                "final_phase": final_phase,
                "best_dev_objective": best_dev,
                "reason": "no_champion" if (final_phase == "no_champion" or not best_ref) else "missing_champion_manifest",
            })
            continue
        raw_solver = json.loads((run_path / best_ref).read_text(encoding="utf-8"))
        raw_solver["solver_id"] = f"{run_path.name}_winner"
        fs = FrozenInterfaceSolver.from_dict(raw_solver)
        by_lane[lane].append({
            "run_dir": str(run_path),
            "lane": lane,
            "run_id": summ.get("run_id"),
            "solver": fs,
            "summary": summ,
        })
    return by_lane, excluded_runs


def _discover_run_solvers(out_dir: Path, lanes: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    by_lane, _ = _discover_run_solvers_with_exclusions(out_dir, lanes)
    return by_lane


def cmd_eval_select(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    by_lane, excluded_runs = _discover_run_solvers_with_exclusions(out_dir, args.lanes)
    gate_reports: dict[str, Any] = {}
    select_results: dict[str, Any] = {}
    selected_winners: dict[str, Any] = {}

    for lane in args.lanes:
        spec = LANE_SPECS[lane]
        family = spec["problem_family"]
        suite = load_dev_or_public_suite(spec["select_suite_id"], split="select", role="selection_tuning")
        # Baseline comparators
        baselines = {}
        for alg in (spec["strong_baseline"], *spec["secondary_baselines"]):
            baselines[alg] = _eval_solver_on_suite(alg, family, suite, time_budget_ms=args.time_budget_ms)

        candidates = []
        validator = InterfaceValidator(
            candidate_timeout_s=derive_effective_batch_timeout_s(12, args.time_budget_ms),
            instance_time_budget_ms=args.time_budget_ms,
        )
        for item in by_lane.get(lane, []):
            fs: FrozenInterfaceSolver = item["solver"]
            design = build_design_for_template(
                fs.template_id, fs.template_version, postprocess_mode=fs.postprocess_mode, rationale="M3.1 gate audit",
            )
            val_rep = validator.validate(design, hook_code_override=fs.hook_code)
            gate_reports[fs.solver_id] = {
                "passed": bool(val_rep.passed),
                "gates": val_rep.gates,
                "diagnostics": val_rep.diagnostics,
            }
            ev = _eval_solver_on_suite(fs, family, suite, time_budget_ms=args.time_budget_ms)
            candidates.append({
                "solver_id": fs.solver_id,
                "template_id": fs.template_id,
                "run_id": item["run_id"],
                "gate_passed": bool(val_rep.passed),
                "completion_rate": ev["completion_rate"],
                "penalized_mean_objective": ev["penalized_mean_objective"],
                "valid_only_mean_objective": ev["valid_only_mean_objective"],
                "solve_ms_mean": ev["solve_ms_mean"],
                "slices": ev["slices"],
                "frozen_solver": fs.to_dict(),
                "records": ev["records"],
            })

        eligible_candidates = [c for c in candidates if c["gate_passed"] and float(c["completion_rate"] or 0.0) > 0.0]
        ranked = sorted(
            eligible_candidates,
            key=lambda c: (not (c["completion_rate"] == 1.0), -c["completion_rate"], float(c["penalized_mean_objective"])),
        )
        winner = ranked[0] if ranked else None
        if winner is not None:
            selected_winners[lane] = winner["solver_id"]
        select_results[lane] = {
            "problem_family": family,
            "protocol_id": spec["protocol_id"],
            "select_suite_id": spec["select_suite_id"],
            "baselines": {k: {kk: vv for kk, vv in v.items() if kk != "records"} for k, v in baselines.items()},
            "candidates": [{k: v for k, v in c.items() if k not in {"records", "frozen_solver"}} for c in candidates],
            "excluded_runs": [e for e in excluded_runs if e["lane"] == lane],
            "winner": ({k: v for k, v in winner.items() if k != "records"} if winner else None),
        }

    # Pick overall winner per problem family (e.g., tsp best across tsp_l1 and tsp_l2)
    family_finalists: dict[str, Any] = {}
    for family in sorted({LANE_SPECS[l]["problem_family"] for l in args.lanes}):
        pool = []
        for lane in args.lanes:
            if LANE_SPECS[lane]["problem_family"] != family:
                continue
            w = select_results[lane]["winner"]
            if w is not None:
                pool.append((lane, w))
        if pool:
            best_lane, best_w = min(
                pool,
                key=lambda item: (
                    not item[1]["gate_passed"],
                    -item[1]["completion_rate"],
                    float(item[1]["penalized_mean_objective"]),
                ),
            )
            family_finalists[family] = {"lane": best_lane, **best_w}

    payload = {
        "schema_version": "m31-selection-report/v1",
        "generated_at": utc_now(),
        "time_budget_ms": float(args.time_budget_ms),
        "lane_results": select_results,
        "excluded_runs": excluded_runs,
        "family_finalists": family_finalists,
        "gate_reports": gate_reports,
    }
    atomic_write_json(out_dir / "m31_selection_report.json", payload)
    print(json.dumps({
        "selection_report": str(out_dir / "m31_selection_report.json"),
        "family_finalists": {k: {"lane": v["lane"], "solver_id": v["solver_id"], "penalized_mean_objective": v["penalized_mean_objective"]} for k, v in family_finalists.items()},
    }, indent=2))
    return 0


def cmd_unseal_blind(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    custody_dir = Path(args.custody_dir).resolve()
    commitment_dir = Path(args.commitment_dir).resolve()
    sel_doc = json.loads((out_dir / "m31_selection_report.json").read_text(encoding="utf-8"))
    finalists = sel_doc.get("family_finalists") or {}
    lane_res = sel_doc.get("lane_results") or {}

    blind_out: dict[str, Any] = {}
    for family in args.families:
        suite_id = m31_suite_id(family, "blind")
        cpath = commitment_dir / f"{suite_id}_commitment.json"
        if not cpath.is_file():
            raise FileNotFoundError(f"missing_m31_commitment:{cpath}")
        c_sha = _sha256_file(cpath)

        # Collect family finalist + lane winners + baselines into ONE single-shot custody open
        dist_conv = "euc_2d_float" if family == "tsp" else "not_applicable"
        veh_pol = "not_applicable"
        proto = M31_PROTOCOL_IDS[family]
        outer_s = derive_effective_batch_timeout_s(1, args.time_budget_ms, floor_s=max(5.0, args.time_budget_ms / 1000.0 + 3.0))

        solvers_for_family: list[tuple[str, FrozenInterfaceSolver]] = []
        for lane, ldata in lane_res.items():
            if LANE_SPECS[lane]["problem_family"] != family:
                continue
            w = ldata.get("winner")
            if w and w.get("frozen_solver"):
                fs = FrozenInterfaceSolver.from_dict(w["frozen_solver"])
                solvers_for_family.append((lane, fs))

        if not solvers_for_family and family in finalists and finalists[family].get("frozen_solver"):
            fs = FrozenInterfaceSolver.from_dict(finalists[family]["frozen_solver"])
            solvers_for_family.append((finalists[family]["lane"], fs))
        if not solvers_for_family:
            raise RuntimeError(f"no_selected_solver_for_family:{family}")

        primary_label, primary_fs = (
            (finalists[family]["lane"], FrozenInterfaceSolver.from_dict(finalists[family]["frozen_solver"]))
            if family in finalists
            else solvers_for_family[0]
        )

        def _make_fs_fn(frozen_s: FrozenInterfaceSolver):
            return lambda inst: evaluate_frozen_interface_solver(
                frozen_s,
                inst,
                distance_convention=dist_conv,
                vehicle_limit_policy=veh_pol,
                solve_deadline_ms=args.time_budget_ms,
                outer_timeout_s=outer_s,
                protocol_id=proto,
            )

        extra_evals: dict[str, Any] = {}
        for label, fs in solvers_for_family:
            if label != primary_label:
                extra_evals[label] = _make_fs_fn(fs)

        # Strong + secondary baselines for this family ONLY
        matching_lanes = [l for l in args.lanes if LANE_SPECS[l]["problem_family"] == family]
        if matching_lanes:
            sp = LANE_SPECS[matching_lanes[0]]
            for alg in (sp["strong_baseline"], *sp["secondary_baselines"]):
                extra_evals[alg] = (lambda a: lambda inst: _eval_baseline_on_instance(
                    a, family, inst, distance_convention=dist_conv, time_budget_ms=args.time_budget_ms,
                ))(alg)

        b_dir = out_dir / f"blind_72_{family}"
        res = unseal_and_evaluate_m31(
            suite_id,
            commitment_path=cpath,
            expected_commitment_sha256=c_sha,
            evaluator=_make_fs_fn(primary_fs),
            output_dir=b_dir,
            custody_dir=custody_dir,
            extra_evaluators=extra_evals,
        )
        blind_out[family] = {
            "suite_id": suite_id,
            "protocol_id": proto,
            "primary_lane": primary_label,
            "primary_solver_id": primary_fs.solver_id,
            "report_path": res["report_path"],
            "report_sha256": res["report_sha256"],
        }

    atomic_write_json(out_dir / "m31_blind_unseal_index.json", {"blind_runs": blind_out})
    print(json.dumps(blind_out, indent=2))
    return 0


def cmd_eval_external(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    sel_doc = json.loads((out_dir / "m31_selection_report.json").read_text(encoding="utf-8"))
    lane_res = sel_doc.get("lane_results") or {}
    finalists = sel_doc.get("family_finalists") or {}
    ext: dict[str, Any] = {}

    # 1. TSPLIB 18
    if any(LANE_SPECS[l]["problem_family"] == "tsp" for l in args.lanes):
        tsplib = load_dev_or_public_suite("tsp_ext_tsplib_euc2d", split="heldout", role="diagnostic_interactive")
        tsp_algos: dict[str, Any] = {}
        for alg in ("tsp_nn_2opt", "tsp_nn", "tsp_farthest_insertion"):
            tsp_algos[alg] = _eval_solver_on_suite(alg, "tsp", tsplib, time_budget_ms=args.time_budget_ms)
        for lane in ("tsp_l1", "tsp_l2"):
            w = (lane_res.get(lane) or {}).get("winner")
            if w and w.get("frozen_solver"):
                tsp_algos[lane] = _eval_solver_on_suite(
                    FrozenInterfaceSolver.from_dict(w["frozen_solver"]), "tsp", tsplib, time_budget_ms=args.time_budget_ms,
                )
        ext["tsp_ext_tsplib_euc2d"] = {
            "suite_id": "tsp_ext_tsplib_euc2d",
            "protocol_id": "tsp/v1",
            "instance_count": len(tsplib["instances"]),
            "algorithms": {k: {kk: vv for kk, vv in v.items() if kk != "records"} for k, v in tsp_algos.items()},
            "per_algorithm_records": {k: v["records"] for k, v in tsp_algos.items()},
        }

    # 2. Online OBP BPPLib 70 (strictly online OBP, never mixed with offline BPP)
    if any(LANE_SPECS[l]["problem_family"] == "obp" for l in args.lanes):
        bpplib = load_dev_or_public_suite("obp_ext_bpplib", split="heldout", role="diagnostic_interactive")
        obp_algos: dict[str, Any] = {}
        for alg in ("obp_best_fit", "obp_first_fit"):
            obp_algos[alg] = _eval_solver_on_suite(alg, "obp", bpplib, time_budget_ms=args.time_budget_ms)
        w = (lane_res.get("obp_online") or {}).get("winner") or finalists.get("obp")
        if w and w.get("frozen_solver"):
            obp_algos["obp_online"] = _eval_solver_on_suite(
                FrozenInterfaceSolver.from_dict(w["frozen_solver"]), "obp", bpplib, time_budget_ms=args.time_budget_ms,
            )
        ext["obp_ext_bpplib"] = {
            "suite_id": "obp_ext_bpplib",
            "protocol_id": "obp_online/v1",
            "instance_count": len(bpplib["instances"]),
            "algorithms": {k: {kk: vv for kk, vv in v.items() if kk != "records"} for k, v in obp_algos.items()},
            "per_algorithm_records": {k: v["records"] for k, v in obp_algos.items()},
        }

    atomic_write_json(out_dir / "external_benchmarks_report.json", ext)
    print(json.dumps({
        k: {"instance_count": v["instance_count"], "means": {ak: av["penalized_mean_objective"] for ak, av in v["algorithms"].items()}}
        for k, v in ext.items()
    }, indent=2))
    return 0


def _summarize_blind_records(recs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(recs)
    ok_vals = [float(r["objective"]) for r in recs if _is_completed_record(r)]
    pens = [
        float(r["objective"])
        if _is_completed_record(r)
        else (2.0 * float(r["reference_objective"]) if r.get("reference_objective") else 1e6)
        for r in recs
    ]
    out_recs = [
        {**dict(r), "penalized_objective": p, "valid": _is_completed_record(r)}
        for r, p in zip(recs, pens)
    ]
    return {
        "instance_count": n,
        "valid_count": len(ok_vals),
        "completion_rate": round(len(ok_vals) / max(1, n), 6),
        "valid_only_mean_objective": round(sum(ok_vals) / len(ok_vals), 6) if ok_vals else None,
        "penalized_mean_objective": round(sum(pens) / max(1, len(pens)), 6) if pens else None,
        "records": out_recs,
    }


def _count_loc(rel_paths: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rp in rel_paths:
        p = REPO / rp
        counts[rp] = len(p.read_text(encoding="utf-8").splitlines()) if p.is_file() else 0
    counts["total_loc"] = sum(counts.values())
    return counts


def cmd_report(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir).resolve()
    sel_doc = json.loads((out_dir / "m31_selection_report.json").read_text(encoding="utf-8"))
    ext_doc = json.loads((out_dir / "external_benchmarks_report.json").read_text(encoding="utf-8")) if (out_dir / "external_benchmarks_report.json").is_file() else {}
    blind_index = json.loads((out_dir / "m31_blind_unseal_index.json").read_text(encoding="utf-8")) if (out_dir / "m31_blind_unseal_index.json").is_file() else {"blind_runs": {}}

    blind_summaries: dict[str, Any] = {}
    raw_pvals: list[tuple[str, float]] = []
    for family, binfo in (blind_index.get("blind_runs") or {}).items():
        bdoc = json.loads(Path(binfo["report_path"]).read_text(encoding="utf-8"))
        primary_sum = _summarize_blind_records(bdoc["records"])
        extras = {
            k: _summarize_blind_records(v)
            for k, v in (bdoc.get("extra_solver_records") or {}).items()
        }
        sp_lanes = [l for l in args.lanes if LANE_SPECS[l]["problem_family"] == family]
        strong_bl = LANE_SPECS[sp_lanes[0]]["strong_baseline"]
        base_sum = extras.get(strong_bl)
        comparisons: dict[str, Any] = {}
        for label, cand_sum in [(binfo["primary_lane"], primary_sum), *[(k, v) for k, v in extras.items() if k in LANE_SPECS]]:
            if base_sum is not None:
                pm = _pair_metrics(cand_sum["records"], base_sum["records"])
                comparisons[f"{label}_vs_{strong_bl}"] = pm
                raw_pvals.append((f"{family}:{label}", float(pm["wilcoxon_p_two_sided"])))
        blind_summaries[family] = {
            "protocol_id": binfo["protocol_id"],
            "strong_baseline": strong_bl,
            "algorithms": {
                binfo["primary_lane"]: {k: v for k, v in primary_sum.items() if k != "records"},
                **{k: {kk: vv for kk, vv in v.items() if kk != "records"} for k, v in extras.items()},
            },
            "comparisons_vs_strong_baseline": comparisons,
        }

    # Holm-Bonferroni adjustment within online+TSP primary tests, keeping BPP independent
    non_bpp = [(k, p) for k, p in raw_pvals if not k.startswith("bpp:")]
    if non_bpp:
        adj = holm_bonferroni_adjust([p for _, p in non_bpp])
        for (tag, _), ap in zip(non_bpp, adj):
            fam, lbl = tag.split(":", 1)
            strong_bl = blind_summaries[fam]["strong_baseline"]
            blind_summaries[fam]["comparisons_vs_strong_baseline"][f"{lbl}_vs_{strong_bl}"]["p_holm_wilcoxon"] = ap

    # Offline BPP keeps its own independent Holm check
    bpp_only = [(k, p) for k, p in raw_pvals if k.startswith("bpp:")]
    if bpp_only:
        adj_bpp = holm_bonferroni_adjust([p for _, p in bpp_only])
        for (tag, _), ap in zip(bpp_only, adj_bpp):
            _, lbl = tag.split(":", 1)
            strong_bl = blind_summaries["bpp"]["strong_baseline"]
            blind_summaries["bpp"]["comparisons_vs_strong_baseline"][f"{lbl}_vs_{strong_bl}"]["p_holm_wilcoxon"] = ap

    code_volume = {fam: _count_loc(paths) for fam, paths in ADDED_CODE_PATHS_BY_FAMILY.items()}
    report = {
        "schema_version": "m31-cross-problem-report/v1",
        "generated_at": utc_now(),
        "selection_summary": sel_doc,
        "excluded_runs": sel_doc.get("excluded_runs") or [],
        "blind_72_main_tsp_and_online_obp": {k: v for k, v in blind_summaries.items() if k != "bpp"},
        "blind_72_independent_offline_bpp": blind_summaries.get("bpp"),
        "external_benchmarks": {
            k: {kk: vv for kk, vv in v.items() if kk != "per_algorithm_records"}
            for k, v in ext_doc.items()
        },
        "added_adapter_template_loc": code_volume,
    }
    atomic_write_json(out_dir / "m31_cross_problem_report.json", report)

    md_lines = [
        "# Milestone 3.1 Cross-Problem Generalization Report",
        "",
        "## 1. Main Track: TSP (`tsp/v1`) & Online OBP (`obp_online/v1`) on Blind-72",
        "",
        "| Family | Protocol | Track / Baseline | Mean Obj | Completion |",
        "|---|---|---|---:|---:|",
    ]
    for fam in ("tsp", "obp"):
        if fam in report["blind_72_main_tsp_and_online_obp"]:
            fdata = report["blind_72_main_tsp_and_online_obp"][fam]
            for aid, adat in fdata["algorithms"].items():
                md_lines.append(f"| {fam} | {fdata['protocol_id']} | {aid} | {adat['penalized_mean_objective']:.4f} | {adat['completion_rate']:.3f} |")
    if report["blind_72_independent_offline_bpp"]:
        bdata = report["blind_72_independent_offline_bpp"]
        md_lines.extend([
            "",
            "## 2. Independent Extension (Strictly Separate): Offline BPP (`bpp_offline/v1`)",
            "",
            "| Track / Baseline | Protocol | Mean Bins | Completion |",
            "|---|---|---:|---:|",
        ])
        for aid, adat in bdata["algorithms"].items():
            md_lines.append(f"| {aid} | {bdata['protocol_id']} | {adat['penalized_mean_objective']:.4f} | {adat['completion_rate']:.3f} |")
    md_lines.extend(["", "## 3. External Benchmarks & Adapter Code Footprint", ""])
    for ename, edata in report["external_benchmarks"].items():
        md_lines.append(f"- **{ename}** (`{edata['protocol_id']}`, N={edata['instance_count']}): " + ", ".join(f"{k}={v['penalized_mean_objective']:.4f}" for k, v in edata["algorithms"].items()))
    for fam, loc in code_volume.items():
        md_lines.append(f"- **{fam}** added adapter+template+probe LOC = {loc['total_loc']}")
    if report["excluded_runs"]:
        md_lines.extend(["", "## 4. Excluded Selection Runs (`no_champion` / Missing)", ""])
        for ex in report["excluded_runs"]:
            md_lines.append(f"- `{ex.get('run_id')}` (lane=`{ex.get('lane')}`, final_phase=`{ex.get('final_phase')}`, reason=`{ex.get('reason')}`)")
    (out_dir / "m31_cross_problem_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps({"report_json": str(out_dir / "m31_cross_problem_report.json"), "report_md": str(out_dir / "m31_cross_problem_report.md")}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Milestone 3.1 Cross-Problem Generalization Runner.")
    p.add_argument("--output-dir", type=Path, default=REPO / "experiments" / "milestone3_1")
    p.add_argument("--custody-dir", type=Path, default=Path.home() / _M31_CUSTODY_NAME)
    p.add_argument("--commitment-dir", type=Path, default=MANIFESTS_DIR)
    p.add_argument("--time-budget-ms", type=float, default=500.0)
    sub = p.add_subparsers(dest="stage", required=True)

    s_bl = sub.add_parser("baseline-check", help="Session baseline freeze & fresh-worker parity check.")
    s_bl.set_defaults(func=cmd_baseline_check)

    s_seal = sub.add_parser("seal-blind", help="Externally seal M3.1 blind-72 suites.")
    s_seal.add_argument("--families", nargs="+", default=["tsp", "obp", "bpp"], choices=["tsp", "obp", "bpp"])
    s_seal.set_defaults(func=cmd_seal_blind)

    s_mux = sub.add_parser("emit-mux", help="Emit tools/multi_task_mux.py manifest JSON.")
    s_mux.add_argument("--lanes", nargs="+", default=list(DEFAULT_LANES), choices=list(LANE_SPECS))
    s_mux.add_argument("--manifest-path", type=Path, default=None)
    s_mux.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    s_mux.add_argument("--mode", choices=("mock", "live"), default="live")
    s_mux.add_argument("--request-cap", type=int, default=36)
    s_mux.add_argument("--max-rounds", type=int, default=3)
    s_mux.add_argument("--eoh-max-sample-nums", type=int, default=6)
    s_mux.add_argument("--model", default="deepseek-v4.1-flash")
    s_mux.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    s_mux.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    s_mux.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    s_mux.set_defaults(func=cmd_emit_mux)

    s_one = sub.add_parser("run-one", help="Run one (lane, seed) experiment.")
    s_one.add_argument("--lane", required=True, choices=list(LANE_SPECS))
    s_one.add_argument("--seed", type=int, required=True)
    s_one.add_argument("--mode", choices=("mock", "live"), default="live")
    s_one.add_argument("--request-cap", type=int, default=36)
    s_one.add_argument("--max-rounds", type=int, default=3)
    s_one.add_argument("--eoh-max-sample-nums", type=int, default=6)
    s_one.add_argument("--model", default="deepseek-v4.1-flash")
    s_one.add_argument("--endpoint", default=os.environ.get("OPENCODE_GO_ENDPOINT", "https://opencode.ai/zen/go/v1/chat/completions"))
    s_one.add_argument("--api-key-env", default="OPENCODE_GO_API_KEY")
    s_one.add_argument("--request-timeout-s", type=float, default=90.0)
    s_one.add_argument("--wall-seconds", type=float, default=1800.0)
    s_one.add_argument("--strict-barriers", action="store_true")
    s_one.add_argument("--resume", action="store_true")
    s_one.set_defaults(func=cmd_run_one)

    s_sel = sub.add_parser("eval-select", help="Evaluate M3.1 selection_36 & behavioral gates.")
    s_sel.add_argument("--lanes", nargs="+", default=list(DEFAULT_LANES), choices=list(LANE_SPECS))
    s_sel.set_defaults(func=cmd_eval_select)

    s_unseal = sub.add_parser("unseal-blind", help="One-shot atomic evaluation of M3.1 blind_72 suites.")
    s_unseal.add_argument("--lanes", nargs="+", default=list(DEFAULT_LANES), choices=list(LANE_SPECS))
    s_unseal.add_argument("--families", nargs="+", default=["tsp", "obp", "bpp"], choices=["tsp", "obp", "bpp"])
    s_unseal.set_defaults(func=cmd_unseal_blind)

    s_ext = sub.add_parser("eval-external", help="Evaluate TSPLIB 18 & BPPLib 70.")
    s_ext.add_argument("--lanes", nargs="+", default=list(DEFAULT_LANES), choices=list(LANE_SPECS))
    s_ext.set_defaults(func=cmd_eval_external)

    s_rep = sub.add_parser("report", help="Generate statistical & summary M3.1 report.")
    s_rep.add_argument("--lanes", nargs="+", default=list(DEFAULT_LANES), choices=list(LANE_SPECS))
    s_rep.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
