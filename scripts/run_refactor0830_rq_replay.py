"""将冻结历史证据重放为 Refactor0830 的 RQ1-RQ4 可审计摘要。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from statistics import median

from eoh_rag.fme.potential import QualityObservation, quality_potential_curve


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _arm_medians(path: Path) -> dict[str, float]:
    runs = _load(path)["runs"]
    grouped: dict[str, list[float]] = {}
    for run in runs:
        match = re.search(r"_(A_pure|B_keyword|C_keyword_outcome|D_keyword_outcome_pop)_", run["tag"])
        if match and run.get("rc") == 0:
            grouped.setdefault(match.group(1), []).append(float(run["best"]))
    return {arm: median(values) for arm, values in grouped.items()}


def _history_effect(path: Path) -> dict[str, object]:
    medians = _arm_medians(path)
    pure = medians["A_pure"]
    outcome = medians["C_keyword_outcome"]
    improvement = (pure - outcome) / abs(pure)
    return {
        "arm_medians": medians,
        "relative_improvement_outcome_vs_pure": improvement,
        "direction": "better" if improvement > 0 else "same_or_worse",
        "paired_seed_count": 3,
    }


def _potential(pool_path: Path, baselines: dict[str, float]) -> dict[str, object]:
    grouped: dict[str, list[dict]] = {problem: [] for problem in baselines}
    for line in pool_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("problem") in grouped:
            grouped[item["problem"]].append(item)
    results = {}
    for problem, runs in grouped.items():
        ordered = sorted(runs, key=lambda item: (float(item["ts"]), item["run_dir"]))
        observations = [
            QualityObservation(index, float(item["objective"]))
            for index, item in enumerate(ordered, start=1)
        ]
        curve = quality_potential_curve(
            initial_objective=float(baselines[problem]),
            observations=observations,
            maximum_budget=len(observations),
        )
        first_five = next((budget for budget, value in curve.points if value >= 0.05), None)
        results[problem] = {
            "completed_runs": len(observations),
            "quality_auc": curve.auc,
            "first_run_budget_reaching_5pct": first_five,
            "final_best_normalized_improvement": curve.points[-1][1],
            "curve": [{"budget": budget, "quality": value} for budget, value in curve.points],
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = _load(root / args.manifest)
    sources = {name: root / path for name, path in manifest["sources"].items()}

    rq1_raw = _load(sources["rq1"])
    rq1_gate = rq1_raw["gate_result"]
    rq1_causal = rq1_raw["offline_causal_analysis"]
    control_valid_rate = rq1_causal["control_valid_generated_candidates"] / rq1_causal["control_submitted_candidates"]
    fme_valid_rate = rq1_causal["fme_valid_generated_candidates"] / rq1_causal["fme_submitted_candidates"]
    rq1 = {
        "status": "mechanism_only_quality_negative",
        "paired_seed_count": rq1_gate["paired_seed_count"],
        "quality_gate": rq1_gate["quality_gate"],
        "mechanism_gate": rq1_gate["mechanism_gate"],
        "median_relative_worst_gap_reduction_pct": rq1_gate["median_relative_worst_gap_reduction_pct"],
        "control_valid_candidate_rate": control_valid_rate,
        "fme_valid_candidate_rate": fme_valid_rate,
        "valid_candidate_rate_delta": fme_valid_rate - control_valid_rate,
        "supported_development_claims": rq1_gate["supported_development_only_claim_count"],
        "admitted_counterexamples": rq1_gate["admitted_counterexample_count"],
    }

    rq2 = {
        "status": "problem_dependent_directional_support_without_shuffled_control",
        "tsp_construct": _history_effect(sources["rq2_tsp"]),
        "cvrp_construct": _history_effect(sources["rq2_cvrp"]),
    }
    rq3_raw = _load(sources["rq3"])
    rq3 = {
        "status": rq3_raw["status"],
        "complete_pairs_by_problem": rq3_raw["complete_pairs_by_problem"],
        "median_relative_gain": rq3_raw["median_relative_gain"],
        "win_tie_loss": [rq3_raw["win"], rq3_raw["tie"], rq3_raw["loss"]],
    }
    deepseek = _load(sources["rq4_deepseek"])
    preflight = _load(sources["provider_preflight"])
    rq4 = {
        "status": "historical_single_model_only_online_blocked",
        "historical_model": deepseek["experiment_config"],
        "historical_problem_summary": deepseek["problems"],
        "model_router_preflight": preflight["result"],
        "cross_model_effect_claim_allowed": False,
        "reason": "JoyAI and DeepSeek historical cohorts do not share one frozen protocol; Model Router DeepSeek V4 Flash permission is unavailable.",
    }

    payload = {
        "schema_version": "refactor0830_rq_replay_result/v1",
        "suite": manifest["suite"],
        "evidence_mode": manifest["evidence_mode"],
        "claim_boundary": manifest["claim_boundary"],
        "source_sha256": {name: _sha256(path) for name, path in sources.items()},
        "RQ1": rq1,
        "RQ2": rq2,
        "RQ3": rq3,
        "RQ4": rq4,
        "quality_potential_curves": _potential(sources["potential_runs"], deepseek["baselines"]),
        "analysis_potential": {
            "status": "not_estimable_from_historical_assets",
            "reason": "Historical analyses were not prospectively frozen; Refactor0830 AnalysisRecord will enable this in the next authorized online cohort."
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "rq1_rq4_offline_replay.json"
    csv_path = args.output_dir / "rq_summary.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["rq", "status", "primary_value", "claim_allowed"])
        writer.writerow(["RQ1", rq1["status"], rq1["median_relative_worst_gap_reduction_pct"], False])
        writer.writerow(["RQ2-CVRP", rq2["status"], rq2["cvrp_construct"]["relative_improvement_outcome_vs_pure"], True])
        writer.writerow(["RQ2-TSP", rq2["status"], rq2["tsp_construct"]["relative_improvement_outcome_vs_pure"], True])
        writer.writerow(["RQ3", rq3["status"], rq3["median_relative_gain"], False])
        writer.writerow(["RQ4", rq4["status"], "", False])
    print(json.dumps({
        "output": str(json_path),
        "RQ1": rq1["status"],
        "RQ2": rq2["status"],
        "RQ3": rq3["status"],
        "RQ4": rq4["status"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
