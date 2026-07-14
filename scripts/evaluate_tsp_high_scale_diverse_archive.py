#!/usr/bin/env python3
"""在未见高规模 TSPLIB 实例上确认功能多样三槽的覆盖。"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_archive_core12 as archive
import intervene_tsp_edge_variability as intervention


RESULT_FIELDS = (
    "instance",
    "nodes",
    "label",
    "archive_membership",
    "code_hash",
    "tour_cost",
    "runtime_seconds",
    "route_hash",
)


def load_protocol(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    actual_hashes = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "archive_metadata_sha256": intervention.sha256_file(args.archive_metadata),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in actual_hashes.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return protocol


def load_candidates(metadata_path: Path, catalog_path: Path) -> list[dict[str, Any]]:
    metadata_by_hash = {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                metadata_by_hash[item["code_hash"]] = item
    resolved = archive.resolve_archive_candidates(metadata_path, catalog_path)
    candidates = []
    for candidate in resolved:
        metadata = metadata_by_hash[candidate["code_hash"]]
        candidates.append(
            {
                **candidate,
                "label": metadata["label"],
                "archive_membership": metadata["archive_membership"],
            }
        )
    if sorted(item["label"] for item in candidates) != ["AW1", "AW2", "AW3", "AW4", "R2", "R4"]:
        raise ValueError("冻结联合档案标签不完整")
    return sorted(candidates, key=lambda item: item["label"])


def edge_jaccard(left: np.ndarray, right: np.ndarray) -> float:
    left_edges = {
        (min(int(a), int(b)), max(int(a), int(b)))
        for a, b in zip(left, np.roll(left, -1))
    }
    right_edges = {
        (min(int(a), int(b)), max(int(a), int(b)))
        for a, b in zip(right, np.roll(right, -1))
    }
    return len(left_edges & right_edges) / len(left_edges | right_edges)


def summarize_instance(
    instance: str,
    rows: list[dict[str, Any]],
    routes: dict[str, np.ndarray],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    by_label = {row["label"]: row for row in rows}
    archives = protocol["archives"]

    def best(labels: list[str]) -> dict[str, Any]:
        return min((by_label[label] for label in labels), key=lambda row: (row["tour_cost"], row["label"]))

    trio = best(archives["frozen_diverse_trio"])
    current = best(archives["current_robust_four"])
    full = best(archives["full_six_oracle"])
    return {
        "instance": instance,
        "nodes": trio["nodes"],
        "trio_winner": trio["label"],
        "current_four_winner": current["label"],
        "full_six_winner": full["label"],
        "trio_cost": trio["tour_cost"],
        "current_four_cost": current["tour_cost"],
        "full_six_cost": full["tour_cost"],
        "trio_regret_to_full_pct": (trio["tour_cost"] / full["tour_cost"] - 1.0) * 100.0,
        "current_four_regret_to_full_pct":
            (current["tour_cost"] / full["tour_cost"] - 1.0) * 100.0,
        "trio_vs_current_cost_delta_pct":
            (trio["tour_cost"] / current["tour_cost"] - 1.0) * 100.0,
        "aw1_aw3_edge_jaccard": edge_jaccard(routes["AW1"], routes["AW3"]),
        "r2_r4_edge_jaccard": edge_jaccard(routes["R2"], routes["R4"]),
    }


def run(args: argparse.Namespace) -> None:
    protocol = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "high_scale_code_results.csv"
    if result_path.exists():
        raise FileExistsError(f"禁止覆盖已有结果：{result_path}")

    instances = intervention.load_instances(args.instance_manifest)
    candidates = load_candidates(args.archive_metadata, args.code_catalog)
    compiled = [(item, intervention.compile_heuristic(item["code"])) for item in candidates]
    result_rows = []
    comparison_rows = []

    for item in instances:
        instance = item["name"]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        instance_rows = []
        routes = {}
        for candidate, heuristic in compiled:
            started = time.perf_counter()
            route, cost = intervention.build_route(heuristic, distances)
            elapsed = time.perf_counter() - started
            row = {
                "instance": instance,
                "nodes": len(coords),
                "label": candidate["label"],
                "archive_membership": candidate["archive_membership"],
                "code_hash": candidate["code_hash"],
                "tour_cost": cost,
                "runtime_seconds": elapsed,
                "route_hash": intervention.route_hash(route),
            }
            instance_rows.append(row)
            result_rows.append(row)
            routes[candidate["label"]] = route
        comparison_rows.append(summarize_instance(instance, instance_rows, routes, protocol))
        del distances, routes
        gc.collect()

    expected_count = int(protocol["evaluation"]["expected_coordinate_count"])
    if len(result_rows) != expected_count or len(
        {(row["instance"], row["label"]) for row in result_rows}
    ) != expected_count:
        raise RuntimeError("高规模坐标数量不完整或重复")

    with result_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(result_rows)
    comparison_path = output_dir / "high_scale_archive_comparison.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    trio_regrets = [float(row["trio_regret_to_full_pct"]) for row in comparison_rows]
    trio_vs_current = [float(row["trio_vs_current_cost_delta_pct"]) for row in comparison_rows]
    wins = sum(value < 0 for value in trio_vs_current)
    losses = sum(value > 0 for value in trio_vs_current)
    gate = protocol["primary_gate"]
    metrics = {
        "instance_count": len(instances),
        "feasible_coordinate_count": len(result_rows),
        "trio_exact_full_oracle_matches": sum(value == 0 for value in trio_regrets),
        "trio_mean_regret_to_full_oracle_pct": statistics.fmean(trio_regrets),
        "trio_median_regret_to_full_oracle_pct": statistics.median(trio_regrets),
        "trio_max_regret_to_full_oracle_pct": max(trio_regrets),
        "trio_vs_current_wins": wins,
        "trio_vs_current_same": len(trio_vs_current) - wins - losses,
        "trio_vs_current_losses": losses,
        "trio_vs_current_median_cost_delta_pct": statistics.median(trio_vs_current),
        "aw1_aw3_identical_route_instances": sum(
            row["aw1_aw3_edge_jaccard"] == 1.0 for row in comparison_rows
        ),
        "median_r2_r4_edge_jaccard": statistics.median(
            float(row["r2_r4_edge_jaccard"]) for row in comparison_rows
        ),
        "median_runtime_seconds_by_code": {
            label: statistics.median(
                float(row["runtime_seconds"]) for row in result_rows if row["label"] == label
            )
            for label in sorted({row["label"] for row in result_rows})
        },
    }
    checks = {
        "feasible_coordinates": metrics["feasible_coordinate_count"]
        >= gate["feasible_coordinate_count_min"],
        "oracle_matches": metrics["trio_exact_full_oracle_matches"]
        >= gate["trio_exact_full_oracle_matches_min"],
        "mean_regret": metrics["trio_mean_regret_to_full_oracle_pct"]
        <= gate["trio_mean_regret_to_full_oracle_pct_max"],
        "max_regret": metrics["trio_max_regret_to_full_oracle_pct"]
        <= gate["trio_max_regret_to_full_oracle_pct_max"],
        "current_direction": wins >= losses,
        "current_median": metrics["trio_vs_current_median_cost_delta_pct"]
        <= gate["trio_vs_current_median_cost_delta_pct_max"],
    }
    summary = {
        "schema_version": "tsp-high-scale-diverse-trio-confirmation/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "metrics": metrics,
        "checks": checks,
        "decision": (
            "diverse_trio_high_scale_supported_but_not_deployed"
            if all(checks.values())
            else "diverse_trio_high_scale_not_supported"
        ),
        "result_sha256": intervention.sha256_file(result_path),
        "comparison_sha256": intervention.sha256_file(comparison_path),
        "default_archive_changed": False,
    }
    summary_path = output_dir / "high_scale_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--archive-metadata", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
