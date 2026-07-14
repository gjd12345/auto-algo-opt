#!/usr/bin/env python3
"""在冻结 TSP 路线上干预边长波动，并与随机局部移动比较。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_archive_core12 as archive


RESULT_FIELDS = (
    "instance",
    "nodes",
    "initial_code_label",
    "initial_route_hash",
    "arm",
    "repetition",
    "steps_applied",
    "initial_cost",
    "final_cost",
    "cost_delta_pct",
    "initial_edge_cv",
    "final_edge_cv",
    "edge_cv_delta",
    "final_route_hash",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def route_hash(route: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(route, dtype=np.int64).tobytes()).hexdigest()


def load_protocol(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": sha256_file(args.instance_manifest),
        "route_behavior_metrics_sha256": sha256_file(args.behavior_metrics),
        "archive_metadata_sha256": sha256_file(args.archive_metadata),
        "code_catalog_sha256": sha256_file(args.code_catalog),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return protocol


def load_instances(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    instances = payload.get("instances", [])
    if len(instances) != payload.get("instance_count"):
        raise ValueError("实例清单数量不一致")
    for item in instances:
        if sha256_file(Path(item["path"])) != item["sha256"]:
            raise RuntimeError(f"实例 hash 不匹配：{item['name']}")
    return instances


def load_pair_candidates(metadata_path: Path, catalog_path: Path) -> list[dict[str, Any]]:
    metadata = []
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                metadata.append(json.loads(line))
    labels_by_hash = {
        item["code_hash"]: item["label"]
        for item in metadata
        if item.get("archive_membership") == "fast_pair"
    }
    candidates = archive.resolve_archive_candidates(metadata_path, catalog_path)
    pair = [
        {**candidate, "label": labels_by_hash[candidate["code_hash"]]}
        for candidate in candidates
        if candidate["code_hash"] in labels_by_hash
    ]
    if sorted(item["label"] for item in pair) != ["R2", "R4"]:
        raise ValueError("冻结快速双槽不是 R2/R4")
    return sorted(pair, key=lambda item: item["label"])


def load_expected_pair_costs(path: Path, pair_hashes: set[str]) -> dict[tuple[str, str], float]:
    expected = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["code_hash"] in pair_hashes:
                expected[(row["code_hash"], row["instance"])] = float(row["tour_cost"])
    return expected


def build_distance_matrix(coords: np.ndarray) -> np.ndarray:
    node_count = len(coords)
    distances = np.empty((node_count, node_count), dtype=float)
    # 分块计算避免一次产生 n×n×2 的临时数组，在 3000 节点实例上降低峰值内存。
    for start in range(0, node_count, 192):
        end = min(start + 192, node_count)
        distances[start:end] = np.rint(
            np.linalg.norm(coords[start:end, None, :] - coords[None, :, :], axis=2)
        )
    distances.setflags(write=False)
    return distances


def compile_heuristic(code: str) -> Any:
    namespace = {"np": np}
    exec(code, namespace)  # 冻结历史代码沿用正式评估入口，不改写其选择逻辑。
    heuristic = namespace.get("select_next_node")
    if not callable(heuristic):
        raise ValueError("select_next_node is missing")
    return heuristic


def build_route(heuristic: Any, distances: np.ndarray) -> tuple[np.ndarray, float]:
    node_count = len(distances)
    route = [0]
    visited = np.zeros(node_count, dtype=bool)
    visited[0] = True
    while len(route) < node_count:
        unvisited = np.flatnonzero(~visited)
        next_node = int(heuristic(route[-1], 0, unvisited, distances))
        if next_node < 0 or next_node >= node_count or visited[next_node]:
            raise ValueError("冻结代码返回了已访问或未知节点")
        route.append(next_node)
        visited[next_node] = True
    route_array = np.asarray(route, dtype=np.int64)
    return route_array, route_cost(route_array, distances)


def edge_lengths(route: np.ndarray, distances: np.ndarray) -> np.ndarray:
    return distances[route, np.roll(route, -1)]


def route_cost(route: np.ndarray, distances: np.ndarray) -> float:
    return float(np.sum(edge_lengths(route, distances)))


def edge_cv(route: np.ndarray, distances: np.ndarray) -> float:
    lengths = edge_lengths(route, distances)
    return float(np.std(lengths) / np.mean(lengths))


def deterministic_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def candidate_pairs(node_count: int, instance: str, step: int, limit: int) -> tuple[np.ndarray, np.ndarray]:
    valid_count = node_count * (node_count - 3) // 2
    if valid_count <= limit:
        left, right = np.triu_indices(node_count, k=2)
        mask = ~((left == 0) & (right == node_count - 1))
        return left[mask], right[mask]

    rng = np.random.default_rng(deterministic_seed(f"{instance}:{step}"))
    pairs: set[tuple[int, int]] = set()
    while len(pairs) < limit:
        batch_size = min((limit - len(pairs)) * 3, 100_000)
        first = rng.integers(0, node_count, size=batch_size)
        second = rng.integers(0, node_count, size=batch_size)
        left = np.minimum(first, second)
        right = np.maximum(first, second)
        for i, j in zip(left.tolist(), right.tolist()):
            if j - i > 1 and not (i == 0 and j == node_count - 1):
                pairs.add((i, j))
                if len(pairs) == limit:
                    break
    ordered = sorted(pairs)
    return (
        np.fromiter((item[0] for item in ordered), dtype=np.int64),
        np.fromiter((item[1] for item in ordered), dtype=np.int64),
    )


def move_outcomes(
    route: np.ndarray,
    distances: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    lengths = edge_lengths(route, distances)
    current_sum = float(np.sum(lengths))
    current_square_sum = float(np.sum(np.square(lengths)))
    node_count = len(route)

    a = route[left]
    b = route[(left + 1) % node_count]
    c = route[right]
    d = route[(right + 1) % node_count]
    old_first = distances[a, b]
    old_second = distances[c, d]
    new_first = distances[a, c]
    new_second = distances[b, d]
    new_sum = current_sum - old_first - old_second + new_first + new_second
    new_square_sum = (
        current_square_sum
        - np.square(old_first)
        - np.square(old_second)
        + np.square(new_first)
        + np.square(new_second)
    )
    new_mean = new_sum / node_count
    new_variance = np.maximum(new_square_sum / node_count - np.square(new_mean), 0.0)
    new_cv = np.sqrt(new_variance) / new_mean
    current_cv = float(np.std(lengths) / np.mean(lengths))
    return new_sum, new_cv, current_sum, current_cv


def apply_two_opt(route: np.ndarray, left: int, right: int) -> np.ndarray:
    updated = route.copy()
    updated[left + 1 : right + 1] = updated[left + 1 : right + 1][::-1]
    return updated


def run_arm(
    initial_route: np.ndarray,
    distances: np.ndarray,
    instance: str,
    arm: str,
    repetition: int,
    maximum_steps: int,
    candidate_limit: int,
) -> tuple[np.ndarray, int]:
    route = initial_route.copy()
    steps_applied = 0
    for step in range(maximum_steps):
        left, right = candidate_pairs(len(route), instance, step, candidate_limit)
        new_sum, new_cv, current_sum, current_cv = move_outcomes(route, distances, left, right)
        if arm == "cv_best":
            index = int(np.argmin(new_cv))
            if new_cv[index] >= current_cv - 1e-12:
                break
        elif arm == "cv_random_positive":
            improving = np.flatnonzero(new_cv < current_cv - 1e-12)
            if len(improving) == 0:
                break
            rng = np.random.default_rng(
                deterministic_seed(f"{instance}:cv-random:{repetition}:{step}")
            )
            index = int(rng.choice(improving))
        elif arm == "cost_best_positive_control":
            index = int(np.argmin(new_sum))
            if new_sum[index] >= current_sum - 1e-12:
                break
        else:
            raise ValueError(f"未知干预臂：{arm}")
        route = apply_two_opt(route, int(left[index]), int(right[index]))
        steps_applied += 1
    return route, steps_applied


def result_row(
    instance: str,
    node_count: int,
    initial_label: str,
    initial_route: np.ndarray,
    final_route: np.ndarray,
    distances: np.ndarray,
    arm: str,
    repetition: int,
    steps_applied: int,
) -> dict[str, Any]:
    initial_cost = route_cost(initial_route, distances)
    final_cost = route_cost(final_route, distances)
    initial_cv = edge_cv(initial_route, distances)
    final_cv = edge_cv(final_route, distances)
    return {
        "instance": instance,
        "nodes": node_count,
        "initial_code_label": initial_label,
        "initial_route_hash": route_hash(initial_route),
        "arm": arm,
        "repetition": repetition,
        "steps_applied": steps_applied,
        "initial_cost": initial_cost,
        "final_cost": final_cost,
        "cost_delta_pct": (final_cost / initial_cost - 1.0) * 100.0,
        "initial_edge_cv": initial_cv,
        "final_edge_cv": final_cv,
        "edge_cv_delta": final_cv - initial_cv,
        "final_route_hash": route_hash(final_route),
    }


def sign_test_p(wins: int, losses: int) -> float:
    count = wins + losses
    if count == 0:
        return 1.0
    tail = sum(math.comb(count, index) for index in range(min(wins, losses) + 1)) / (2**count)
    return min(1.0, 2.0 * tail)


def summarize(results: list[dict[str, Any]], protocol: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        by_instance.setdefault(row["instance"], []).append(row)

    comparisons = []
    for instance, rows in sorted(by_instance.items()):
        cv_best = next(row for row in rows if row["arm"] == "cv_best")
        positive = next(row for row in rows if row["arm"] == "cost_best_positive_control")
        random_rows = [row for row in rows if row["arm"] == "cv_random_positive"]
        random_median_cost = statistics.median(float(row["final_cost"]) for row in random_rows)
        comparisons.append(
            {
                "instance": instance,
                "nodes": cv_best["nodes"],
                "initial_cost": cv_best["initial_cost"],
                "cv_best_final_cost": cv_best["final_cost"],
                "cv_best_cost_delta_pct": cv_best["cost_delta_pct"],
                "cv_best_edge_cv_delta": cv_best["edge_cv_delta"],
                "random_median_final_cost": random_median_cost,
                "cv_best_vs_random_cost_delta_pct":
                    (float(cv_best["final_cost"]) / random_median_cost - 1.0) * 100.0,
                "positive_control_cost_delta_pct": positive["cost_delta_pct"],
            }
        )

    cv_wins = sum(row["cv_best_cost_delta_pct"] < 0 for row in comparisons)
    cv_losses = sum(row["cv_best_cost_delta_pct"] > 0 for row in comparisons)
    random_wins = sum(row["cv_best_vs_random_cost_delta_pct"] < 0 for row in comparisons)
    random_losses = sum(row["cv_best_vs_random_cost_delta_pct"] > 0 for row in comparisons)
    instance_count = len(comparisons)
    metrics = {
        "instance_count": instance_count,
        "cv_reduction_instance_rate": sum(row["cv_best_edge_cv_delta"] < 0 for row in comparisons)
        / instance_count,
        "cv_best_cost_wins": cv_wins,
        "cv_best_cost_same": instance_count - cv_wins - cv_losses,
        "cv_best_cost_losses": cv_losses,
        "cv_best_median_cost_delta_pct": statistics.median(
            row["cv_best_cost_delta_pct"] for row in comparisons
        ),
        "cv_best_two_sided_sign_test_p": sign_test_p(cv_wins, cv_losses),
        "cv_best_vs_random_wins": random_wins,
        "cv_best_vs_random_same": instance_count - random_wins - random_losses,
        "cv_best_vs_random_losses": random_losses,
        "cv_best_vs_random_median_cost_delta_pct": statistics.median(
            row["cv_best_vs_random_cost_delta_pct"] for row in comparisons
        ),
        "positive_control_cost_improvement_instance_rate": sum(
            row["positive_control_cost_delta_pct"] < 0 for row in comparisons
        )
        / instance_count,
        "feasible_rate": 1.0,
    }
    gate = protocol["primary_gate"]
    checks = {
        "manipulation": metrics["cv_reduction_instance_rate"]
        >= gate["cv_best_cv_reduction_instance_rate_min"],
        "cost_direction": metrics["cv_best_cost_wins"] > metrics["cv_best_cost_losses"],
        "cost_median": metrics["cv_best_median_cost_delta_pct"]
        <= gate["cv_best_median_cost_delta_pct_max"],
        "cost_sign_test": metrics["cv_best_two_sided_sign_test_p"]
        <= gate["cv_best_two_sided_sign_test_p_max"],
        "random_direction": metrics["cv_best_vs_random_wins"]
        > metrics["cv_best_vs_random_losses"],
        "random_median": metrics["cv_best_vs_random_median_cost_delta_pct"]
        <= gate["cv_best_vs_random_median_cost_delta_pct_max"],
        "positive_control": metrics["positive_control_cost_improvement_instance_rate"]
        >= gate["positive_control_cost_improvement_instance_rate_min"],
        "feasible": metrics["feasible_rate"] >= gate["feasible_rate_min"],
    }
    if not checks["manipulation"]:
        decision = "intervention_invalid"
    elif all(checks.values()):
        decision = "edge_variability_has_actionable_intervention_support"
    else:
        decision = "edge_variability_is_predictive_but_not_actionable_under_this_intervention"
    return {"metrics": metrics, "checks": checks, "decision": decision}, comparisons


def run(args: argparse.Namespace) -> None:
    protocol = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "intervention_results.csv"
    if result_path.exists():
        raise FileExistsError(f"禁止覆盖已有干预结果：{result_path}")

    instances = load_instances(args.instance_manifest)
    candidates = load_pair_candidates(args.archive_metadata, args.code_catalog)
    expected_costs = load_expected_pair_costs(
        args.behavior_metrics, {item["code_hash"] for item in candidates}
    )
    heuristics = [(item, compile_heuristic(item["code"])) for item in candidates]
    maximum_steps = int(protocol["move"]["maximum_steps"])
    candidate_limit = int(protocol["move"]["candidate_pairs_per_step"])
    random_repetitions = next(
        int(item["repetitions"])
        for item in protocol["arms"]
        if item["name"] == "cv_random_positive"
    )

    results = []
    for item in instances:
        instance = item["name"]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = build_distance_matrix(coords)
        initial_candidates = []
        for candidate, heuristic in heuristics:
            route, cost = build_route(heuristic, distances)
            expected = expected_costs.get((candidate["code_hash"], instance))
            if expected is None or cost != expected:
                raise RuntimeError(
                    f"路线重放与 Stage BH 不一致：{instance} {candidate['label']} "
                    f"expected={expected} actual={cost}"
                )
            initial_candidates.append((cost, candidate["label"], route))
        _, initial_label, initial_route = min(initial_candidates, key=lambda row: (row[0], row[1]))

        for arm, repetitions in (
            ("cv_best", 1),
            ("cv_random_positive", random_repetitions),
            ("cost_best_positive_control", 1),
        ):
            for repetition in range(repetitions):
                final_route, steps = run_arm(
                    initial_route,
                    distances,
                    instance,
                    arm,
                    repetition,
                    maximum_steps,
                    candidate_limit,
                )
                results.append(
                    result_row(
                        instance,
                        len(coords),
                        initial_label,
                        initial_route,
                        final_route,
                        distances,
                        arm,
                        repetition,
                        steps,
                    )
                )

    with result_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    summary, comparisons = summarize(results, protocol)
    comparison_path = output_dir / "intervention_comparison_by_instance.csv"
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    summary.update(
        {
            "schema_version": "tsp-edge-variability-intervention/v1",
            "protocol_sha256": sha256_file(args.protocol),
            "result_sha256": sha256_file(result_path),
            "comparison_sha256": sha256_file(comparison_path),
            "result_row_count": len(results),
            "unique_result_coordinate_count": len(
                {(row["instance"], row["arm"], row["repetition"]) for row in results}
            ),
        }
    )
    summary_path = output_dir / "intervention_summary.json"
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
