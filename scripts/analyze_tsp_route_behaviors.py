#!/usr/bin/env python3
"""重放冻结 TSP 代码并提取路线行为，解释档案在不同实例上的胜负。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np

import audit_tsp_history_scalability as audit
import evaluate_tsp_archive_core12 as archive


RESULT_FIELDS = (
    "code_hash",
    "instance",
    "nodes",
    "tour_cost",
    "edge_length_cv",
    "long_edge_share",
    "nearest_choice_rate",
    "median_chosen_neighbor_rank",
    "p90_chosen_neighbor_rank",
    "sampled_crossing_rate",
    "sampled_edge_pair_count",
)


def load_tsp(path: Path) -> dict[str, Any]:
    example_dir = audit.REPO_ROOT / "official_eoh/examples"
    sys.path.insert(0, str(example_dir))
    from core_benchmarks import load_tsp as load_core_tsp  # pylint: disable=import-outside-toplevel

    return load_core_tsp(path)


def build_route(code: str, coords: np.ndarray) -> tuple[list[int], np.ndarray, float]:
    namespace = {"np": np}
    exec(code, namespace)  # 历史代码与正式 held-out 评估器使用同一编译入口。
    heuristic = namespace.get("select_next_node")
    if not callable(heuristic):
        raise ValueError("select_next_node is missing")

    distances = np.rint(np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2))
    distances.setflags(write=False)
    route = [0]
    visited = np.zeros(len(coords), dtype=bool)
    visited[0] = True
    while len(route) < len(coords):
        unvisited = np.flatnonzero(~visited)
        next_node = int(heuristic(route[-1], 0, unvisited, distances))
        if next_node < 0 or next_node >= len(coords) or visited[next_node]:
            raise ValueError("heuristic returned visited or unknown node")
        route.append(next_node)
        visited[next_node] = True
    route_array = np.asarray(route, dtype=int)
    edge_lengths = distances[route_array, np.roll(route_array, -1)]
    return route, distances, float(np.sum(edge_lengths))


def sampled_crossing_rate(coords: np.ndarray, route: list[int], instance: str) -> tuple[float, int]:
    node_count = len(route)
    if node_count <= 500:
        left, right = np.triu_indices(node_count, k=1)
        mask = (right - left > 1) & ~((left == 0) & (right == node_count - 1))
        left, right = left[mask], right[mask]
    else:
        # 大实例只抽固定上限的非相邻边对；seed 只由实例名决定，便于不同代码公平比较。
        seed = int(hashlib.sha256(instance.encode("utf-8")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        sample_count = 100_000
        left = rng.integers(0, node_count, size=sample_count * 2)
        right = rng.integers(0, node_count, size=sample_count * 2)
        distance = np.abs(left - right)
        mask = (left != right) & (distance != 1) & (distance != node_count - 1)
        left, right = left[mask][:sample_count], right[mask][:sample_count]

    route_array = np.asarray(route, dtype=int)
    edge_start = coords[route_array]
    edge_end = coords[np.roll(route_array, -1)]
    a, b = edge_start[left], edge_end[left]
    c, d = edge_start[right], edge_end[right]

    def orientation(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> np.ndarray:
        return (q[:, 0] - p[:, 0]) * (r[:, 1] - p[:, 1]) - (q[:, 1] - p[:, 1]) * (
            r[:, 0] - p[:, 0]
        )

    crosses = (orientation(a, b, c) * orientation(a, b, d) < 0) & (
        orientation(c, d, a) * orientation(c, d, b) < 0
    )
    return float(np.mean(crosses)) if len(crosses) else 0.0, len(crosses)


def route_metrics(
    code_hash: str,
    instance: str,
    coords: np.ndarray,
    route: list[int],
    distances: np.ndarray,
    tour_cost: float,
) -> dict[str, Any]:
    route_array = np.asarray(route, dtype=int)
    edge_lengths = distances[route_array, np.roll(route_array, -1)]
    positive_edges = edge_lengths[edge_lengths > 0]
    edge_median = float(np.median(positive_edges)) if len(positive_edges) else 0.0

    visited = np.zeros(len(route), dtype=bool)
    visited[route[0]] = True
    chosen_ranks = []
    for current, next_node in zip(route, route[1:]):
        unvisited = np.flatnonzero(~visited)
        chosen_distance = distances[current, next_node]
        chosen_ranks.append(1 + int(np.sum(distances[current, unvisited] < chosen_distance)))
        visited[next_node] = True

    crossing_rate, pair_count = sampled_crossing_rate(coords, route, instance)
    return {
        "code_hash": code_hash,
        "instance": instance,
        "nodes": len(route),
        "tour_cost": tour_cost,
        "edge_length_cv": float(np.std(edge_lengths) / np.mean(edge_lengths)),
        "long_edge_share": float(np.mean(edge_lengths > 2 * edge_median)) if edge_median else 0.0,
        "nearest_choice_rate": float(np.mean(np.asarray(chosen_ranks) == 1)),
        "median_chosen_neighbor_rank": float(np.median(chosen_ranks)),
        "p90_chosen_neighbor_rank": float(np.percentile(chosen_ranks, 90)),
        "sampled_crossing_rate": crossing_rate,
        "sampled_edge_pair_count": pair_count,
    }


def read_expected_costs(path: Path) -> dict[tuple[str, str], float]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {
            (row["code_hash"], row["instance"]): float(row["tour_cost"])
            for row in csv.DictReader(handle)
            if row.get("feasible") == "True"
        }


def load_instance_entries(instance_manifest: Path | None) -> tuple[list[dict[str, Any]], str | None]:
    if instance_manifest is None:
        return [
            {"instance": item["instance"], "path": audit.REPO_ROOT / item["path"]}
            for item in audit.load_tsp_registry()
        ], None

    manifest_path = instance_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = []
    for item in manifest.get("instances", []):
        path = Path(item["path"])
        if audit.sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"外部实例 hash 不匹配：{item['name']}")
        entries.append({"instance": item["name"], "path": path})
    if not entries or len(entries) != manifest.get("instance_count"):
        raise ValueError("外部实例 manifest 为空或数量不一致")
    return entries, audit.sha256_file(manifest_path)


def run(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "route_behavior_metrics.csv"
    if output_path.exists():
        raise FileExistsError(f"行为结果已存在，禁止覆盖：{output_path}")

    archive_path = args.archive_path.resolve()
    catalog_path = args.catalog_path.resolve()
    candidates = archive.resolve_archive_candidates(archive_path, catalog_path)
    expected_path = args.expected_results.resolve() if args.expected_results else None
    expected_costs = read_expected_costs(expected_path) if expected_path else None
    instances, instance_manifest_sha256 = load_instance_entries(args.instance_manifest)
    rows = []
    for candidate in candidates:
        for item in instances:
            instance = item["instance"]
            data = load_tsp(item["path"])
            route, distances, tour_cost = build_route(candidate["code"], data["coords"])
            expected_cost = (
                expected_costs.get((candidate["code_hash"], instance)) if expected_costs else None
            )
            if expected_costs is not None and (expected_cost is None or tour_cost != expected_cost):
                raise RuntimeError(
                    f"路线成本与冻结结果不一致：{candidate['code_hash']} {instance} "
                    f"expected={expected_cost} actual={tour_cost}"
                )
            rows.append(
                route_metrics(
                    candidate["code_hash"], instance, data["coords"], route, distances, tour_cost
                )
            )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "schema_version": "tsp-route-behavior-analysis/v1",
        "repo_commit": audit.current_commit(),
        "archive_sha256": audit.sha256_file(archive_path),
        "catalog_sha256": audit.sha256_file(catalog_path),
        "instance_manifest_sha256": instance_manifest_sha256,
        "expected_results_sha256": audit.sha256_file(expected_path) if expected_path else None,
        "coordinate_count": len(rows),
        "unique_coordinate_count": len({(row["code_hash"], row["instance"]) for row in rows}),
        "median_sampled_edge_pair_count": statistics.median(
            row["sampled_edge_pair_count"] for row in rows
        ),
        "tour_costs_match_frozen_results": True if expected_path else None,
    }
    audit.write_json(output_dir / "route_behavior_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path, required=True)
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path)
    parser.add_argument("--expected-results", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
