"""分析 BP FME 六运行配对 pilot，并按冻结门槛给出自动决策。"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path
from typing import Any


CONTROL_ARM = "scalar_reflection_control"
FME_ARM = "falsifiable_mechanism_ecology"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _heldout_payload(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "held_out_report.json"
    if not path.is_file():
        raise FileNotFoundError(f"held-out report missing: {path}")
    payload = _load_json(path)
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"held-out report invalid: {path}")
    return payload


def _worst_gap(report: dict[str, Any]) -> float:
    return max(float(row["mean_gap_pct"]) for row in report.values())


def _paired_instance_differences(
    control: dict[str, Any], fme: dict[str, Any]
) -> dict[str, list[float]]:
    differences = {}
    for suite in sorted(set(control) & set(fme)):
        control_values = control[suite]["instance_gap_pct"]
        fme_values = fme[suite]["instance_gap_pct"]
        if len(control_values) != len(fme_values):
            raise ValueError(f"held-out instance count mismatch for {suite}")
        differences[suite] = [
            float(control_gap) - float(fme_gap)
            for control_gap, fme_gap in zip(control_values, fme_values)
        ]
    return differences


def _stratified_bootstrap_interval(
    differences_by_seed: dict[int, dict[str, list[float]]],
    *,
    samples: int = 10000,
    seed: int = 23000,
) -> tuple[float, float]:
    """先重采样 seed，再在每个 seed 的各 suite 内重采样配对实例。"""
    rng = random.Random(seed)
    seed_ids = sorted(differences_by_seed)
    bootstrap_means = []
    for _ in range(samples):
        sampled_differences = []
        for sampled_seed in rng.choices(seed_ids, k=len(seed_ids)):
            for values in differences_by_seed[sampled_seed].values():
                sampled_differences.extend(rng.choices(values, k=len(values)))
        bootstrap_means.append(statistics.fmean(sampled_differences))
    return _quantile(bootstrap_means, 0.025), _quantile(bootstrap_means, 0.975)


def _fme_archive_evidence(run_dirs: list[Path]) -> dict[str, int]:
    behavior_profiles = set()
    supported_claims = set()
    counterexamples = set()
    for run_dir in run_dirs:
        archive_dir = run_dir / "results" / "fme_evidence" / "archives"
        algorithm_path = archive_dir / "algorithm_archive.jsonl"
        if algorithm_path.is_file():
            for line in algorithm_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "admit":
                    behavior_profiles.add(
                        event["profile"]["behavior_profile_hash"]
                    )
        claim_path = archive_dir / "mechanism_claim_archive.jsonl"
        if claim_path.is_file():
            for line in claim_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "transition" and event.get("to_state") == "supported":
                    supported_claims.add(event["claim_id"])
        counterexample_path = archive_dir / "counterexample_archive.jsonl"
        if counterexample_path.is_file():
            for line in counterexample_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event") == "admit":
                    counterexamples.add(event["artifact"]["counterexample_id"])
    return {
        "new_behavior_profile_count": len(behavior_profiles),
        "supported_claim_count": len(supported_claims),
        "admitted_counterexample_count": len(counterexamples),
    }


def analyze(run_index_path: Path) -> dict[str, Any]:
    rows = _load_json(run_index_path)
    indexed = {(str(row["arm"]), int(row["seed"])): row for row in rows}
    expected = {(arm, seed) for arm in (CONTROL_ARM, FME_ARM) for seed in (23001, 23002, 23003)}
    missing = sorted(expected - set(indexed))
    incomplete = sorted(
        [key for key in expected & set(indexed) if indexed[key].get("status") not in {"ok", "skipped_complete"}]
    )
    if missing or incomplete:
        return {
            "status": "inconclusive",
            "automatic_decision": "resume_missing_frozen_coordinates_only",
            "missing_coordinates": missing,
            "incomplete_coordinates": incomplete,
        }

    paired_rows = []
    differences_by_seed = {}
    fme_run_dirs = []
    for seed in (23001, 23002, 23003):
        control_dir = Path(indexed[(CONTROL_ARM, seed)]["output_dir"])
        fme_dir = Path(indexed[(FME_ARM, seed)]["output_dir"])
        control_report = _heldout_payload(control_dir)
        fme_report = _heldout_payload(fme_dir)
        control_worst = _worst_gap(control_report)
        fme_worst = _worst_gap(fme_report)
        relative_reduction = (
            (control_worst - fme_worst) / max(abs(control_worst), 1e-12) * 100.0
        )
        paired_rows.append(
            {
                "seed": seed,
                "control_worst_gap_pct": control_worst,
                "fme_worst_gap_pct": fme_worst,
                "relative_reduction_pct": relative_reduction,
                "fme_better": fme_worst < control_worst,
            }
        )
        differences_by_seed[seed] = _paired_instance_differences(
            control_report, fme_report
        )
        fme_run_dirs.append(fme_dir)

    interval = _stratified_bootstrap_interval(differences_by_seed)
    archive_evidence = _fme_archive_evidence(fme_run_dirs)
    directional_pairs = sum(row["fme_better"] for row in paired_rows)
    median_reduction = statistics.median(
        row["relative_reduction_pct"] for row in paired_rows
    )
    mechanism_gate = (
        archive_evidence["new_behavior_profile_count"] >= 1
        and archive_evidence["supported_claim_count"] >= 1
        and archive_evidence["admitted_counterexample_count"] >= 1
    )
    quality_gate = (
        directional_pairs == 3
        and median_reduction >= 2.0
        and interval[0] > 0.0
    )
    if quality_gate and mechanism_gate:
        decision = "freeze_discovery_packet_and_prepare_unlaunched_tsp_cvrp_transfer_manifest"
        status = "pass"
    elif mechanism_gate:
        decision = "record_tentative_innovation_and_run_offline_causal_analysis_only"
        status = "mechanism_only"
    else:
        decision = "record_negative_result_and_stop_current_fme_representation"
        status = "complete_fail"
    return {
        "status": status,
        "automatic_decision": decision,
        "completed_runs": 6,
        "paired_seed_count": 3,
        "directional_pairs": directional_pairs,
        "median_relative_worst_gap_reduction_pct": median_reduction,
        "stratified_bootstrap_mean_difference_95pct": list(interval),
        "quality_gate": quality_gate,
        "mechanism_gate": mechanism_gate,
        "archive_evidence": archive_evidence,
        "paired_results": paired_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-index", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.run_index))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
