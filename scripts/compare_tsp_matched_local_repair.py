#!/usr/bin/env python3
"""对快速双槽和稳健四槽施加匹配局部修复，判断差异来自局部还是全局。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_archive_core12 as archive
import intervene_tsp_edge_variability as intervention


REPAIR_FIELDS = (
    "instance",
    "nodes",
    "archive",
    "initial_code_label",
    "initial_route_hash",
    "initial_cost",
    "repaired_cost",
    "repair_cost_delta_pct",
    "steps_applied",
    "repaired_route_hash",
)


def load_protocol(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    actual_hashes = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "route_behavior_metrics_sha256": intervention.sha256_file(args.behavior_metrics),
        "archive_metadata_sha256": intervention.sha256_file(args.archive_metadata),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in actual_hashes.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return protocol


def load_candidates(metadata_path: Path, catalog_path: Path) -> list[dict[str, Any]]:
    labels_by_hash = {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                labels_by_hash[item["code_hash"]] = item["label"]
    candidates = archive.resolve_archive_candidates(metadata_path, catalog_path)
    labeled = [
        {**candidate, "label": labels_by_hash[candidate["code_hash"]]}
        for candidate in candidates
    ]
    if sorted(item["label"] for item in labeled) != ["AW1", "AW2", "AW3", "AW4", "R2", "R4"]:
        raise ValueError("冻结联合档案标签不完整")
    return sorted(labeled, key=lambda item: item["label"])


def load_expected_costs(path: Path) -> dict[tuple[str, str], float]:
    expected = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            expected[(row["code_hash"], row["instance"])] = float(row["tour_cost"])
    return expected


def repair_row(
    instance: str,
    node_count: int,
    archive_name: str,
    label: str,
    initial_route: np.ndarray,
    repaired_route: np.ndarray,
    distances: np.ndarray,
    steps: int,
) -> dict[str, Any]:
    initial_cost = intervention.route_cost(initial_route, distances)
    repaired_cost = intervention.route_cost(repaired_route, distances)
    return {
        "instance": instance,
        "nodes": node_count,
        "archive": archive_name,
        "initial_code_label": label,
        "initial_route_hash": intervention.route_hash(initial_route),
        "initial_cost": initial_cost,
        "repaired_cost": repaired_cost,
        "repair_cost_delta_pct": (repaired_cost / initial_cost - 1.0) * 100.0,
        "steps_applied": steps,
        "repaired_route_hash": intervention.route_hash(repaired_route),
    }


def direction(delta: float) -> str:
    if delta < 0:
        return "pair_better"
    if delta > 0:
        return "pair_worse"
    return "same"


def build_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["instance"], {})[row["archive"]] = row

    comparisons = []
    for instance, archives in sorted(grouped.items()):
        pair = archives["fast_pair"]
        robust = archives["robust_four"]
        before_delta = (pair["initial_cost"] / robust["initial_cost"] - 1.0) * 100.0
        after_delta = (pair["repaired_cost"] / robust["repaired_cost"] - 1.0) * 100.0
        before_abs = abs(before_delta)
        after_abs = abs(after_delta)
        if after_abs < before_abs - 1e-12:
            gap_change = "shrink"
        elif after_abs > before_abs + 1e-12:
            gap_change = "expand"
        else:
            gap_change = "same"
        comparisons.append(
            {
                "instance": instance,
                "nodes": pair["nodes"],
                "pair_initial_label": pair["initial_code_label"],
                "robust_initial_label": robust["initial_code_label"],
                "pair_repair_delta_pct": pair["repair_cost_delta_pct"],
                "robust_repair_delta_pct": robust["repair_cost_delta_pct"],
                "before_pair_vs_robust_delta_pct": before_delta,
                "after_pair_vs_robust_delta_pct": after_delta,
                "before_absolute_gap_pct": before_abs,
                "after_absolute_gap_pct": after_abs,
                "gap_change": gap_change,
                "before_direction": direction(before_delta),
                "after_direction": direction(after_delta),
                "direction_flipped": direction(before_delta) != direction(after_delta),
            }
        )
    return comparisons


def summarize(
    repair_rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    before_values = [float(row["before_pair_vs_robust_delta_pct"]) for row in comparisons]
    after_values = [float(row["after_pair_vs_robust_delta_pct"]) for row in comparisons]
    before_abs = [abs(value) for value in before_values]
    after_abs = [abs(value) for value in after_values]
    before_median_abs = statistics.median(before_abs)
    after_median_abs = statistics.median(after_abs)
    shrink = sum(row["gap_change"] == "shrink" for row in comparisons)
    expand = sum(row["gap_change"] == "expand" for row in comparisons)
    same = len(comparisons) - shrink - expand

    repair_by_archive = {}
    for archive_name in ("fast_pair", "robust_four"):
        values = [
            float(row["repair_cost_delta_pct"])
            for row in repair_rows
            if row["archive"] == archive_name
        ]
        repair_by_archive[archive_name] = {
            "median_cost_delta_pct": statistics.median(values),
            "improved_instances": sum(value < 0 for value in values),
            "same_instances": sum(value == 0 for value in values),
            "worse_instances": sum(value > 0 for value in values),
        }

    reduction_fraction = (
        1.0 - after_median_abs / before_median_abs if before_median_abs > 0 else 0.0
    )
    metrics = {
        "instance_count": len(comparisons),
        "before_pair_better": sum(value < 0 for value in before_values),
        "before_same": sum(value == 0 for value in before_values),
        "before_pair_worse": sum(value > 0 for value in before_values),
        "before_median_pair_vs_robust_delta_pct": statistics.median(before_values),
        "after_pair_better": sum(value < 0 for value in after_values),
        "after_same": sum(value == 0 for value in after_values),
        "after_pair_worse": sum(value > 0 for value in after_values),
        "after_median_pair_vs_robust_delta_pct": statistics.median(after_values),
        "before_median_absolute_gap_pct": before_median_abs,
        "after_median_absolute_gap_pct": after_median_abs,
        "median_absolute_gap_reduction_fraction": reduction_fraction,
        "gap_shrink_instances": shrink,
        "gap_same_instances": same,
        "gap_expand_instances": expand,
        "gap_shrink_two_sided_sign_test_p": intervention.sign_test_p(shrink, expand),
        "direction_flip_instances": sum(row["direction_flipped"] for row in comparisons),
        "repair_by_archive": repair_by_archive,
        "feasible_rate": 1.0,
    }
    gate = protocol["primary_gate"]
    checks = {
        "median_gap_reduction": reduction_fraction
        >= gate["median_absolute_archive_gap_reduction_fraction_min"],
        "shrink_direction": shrink > expand,
        "shrink_sign_test": metrics["gap_shrink_two_sided_sign_test_p"]
        <= gate["gap_shrink_two_sided_sign_test_p_max"],
        "feasible": metrics["feasible_rate"] >= gate["feasible_rate_min"],
    }
    decision = (
        "archive_difference_is_substantially_locally_repairable"
        if all(checks.values())
        else "archive_difference_persists_beyond_matched_local_repair"
    )
    return {"metrics": metrics, "checks": checks, "decision": decision}


def run(args: argparse.Namespace) -> None:
    protocol = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    repair_path = output_dir / "matched_repair_results.csv"
    if repair_path.exists():
        raise FileExistsError(f"禁止覆盖已有结果：{repair_path}")

    instances = intervention.load_instances(args.instance_manifest)
    candidates = load_candidates(args.archive_metadata, args.code_catalog)
    expected = load_expected_costs(args.behavior_metrics)
    heuristics = [(item, intervention.compile_heuristic(item["code"])) for item in candidates]
    groups = protocol["archives"]
    maximum_steps = int(protocol["repair"]["maximum_steps"])
    candidate_limit = int(protocol["repair"]["candidate_pairs_per_step"])

    repair_rows = []
    for item in instances:
        instance = item["name"]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        routes = {}
        for candidate, heuristic in heuristics:
            route, cost = intervention.build_route(heuristic, distances)
            expected_cost = expected.get((candidate["code_hash"], instance))
            if expected_cost is None or cost != expected_cost:
                raise RuntimeError(
                    f"路线重放与 Stage BH 不一致：{instance} {candidate['label']} "
                    f"expected={expected_cost} actual={cost}"
                )
            routes[candidate["label"]] = (cost, route)

        for archive_name, labels in (
            ("fast_pair", groups["fast_pair"]),
            ("robust_four", groups["robust_four"]),
        ):
            label, (_, initial_route) = min(
                ((label, routes[label]) for label in labels),
                key=lambda entry: (entry[1][0], entry[0]),
            )
            repaired_route, steps = intervention.run_arm(
                initial_route,
                distances,
                instance,
                "cost_best_positive_control",
                0,
                maximum_steps,
                candidate_limit,
            )
            repair_rows.append(
                repair_row(
                    instance,
                    len(coords),
                    archive_name,
                    label,
                    initial_route,
                    repaired_route,
                    distances,
                    steps,
                )
            )

    with repair_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPAIR_FIELDS)
        writer.writeheader()
        writer.writerows(repair_rows)

    comparisons = build_comparisons(repair_rows)
    comparison_path = output_dir / "matched_repair_comparison_by_instance.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    summary = summarize(repair_rows, comparisons, protocol)
    summary.update(
        {
            "schema_version": "tsp-matched-archive-local-repair/v1",
            "protocol_sha256": intervention.sha256_file(args.protocol),
            "repair_result_sha256": intervention.sha256_file(repair_path),
            "comparison_sha256": intervention.sha256_file(comparison_path),
            "repair_row_count": len(repair_rows),
            "unique_repair_coordinate_count": len(
                {(row["instance"], row["archive"]) for row in repair_rows}
            ),
        }
    )
    summary_path = output_dir / "matched_repair_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--behavior-metrics", type=Path, required=True)
    parser.add_argument("--archive-metadata", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
