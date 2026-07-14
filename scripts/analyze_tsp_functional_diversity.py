#!/usr/bin/env python3
"""分析冻结 TSP 代码的路线家族相似度、槽位贡献和档案覆盖前沿。"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_archive_core12 as archive
import intervene_tsp_edge_variability as intervention


def load_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan = json.loads(args.analysis_plan.read_text(encoding="utf-8"))
    actual_hashes = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "route_behavior_metrics_sha256": intervention.sha256_file(args.behavior_metrics),
        "archive_metadata_sha256": intervention.sha256_file(args.archive_metadata),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in actual_hashes.items():
        if plan["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return plan


def load_candidates(metadata_path: Path, catalog_path: Path) -> list[dict[str, Any]]:
    metadata_by_hash = {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                metadata_by_hash[item["code_hash"]] = item
    candidates = archive.resolve_archive_candidates(metadata_path, catalog_path)
    labeled = []
    for candidate in candidates:
        metadata = metadata_by_hash[candidate["code_hash"]]
        labeled.append(
            {
                **candidate,
                "label": metadata["label"],
                "archive_membership": metadata["archive_membership"],
            }
        )
    if sorted(item["label"] for item in labeled) != ["AW1", "AW2", "AW3", "AW4", "R2", "R4"]:
        raise ValueError("冻结联合档案标签不完整")
    return sorted(labeled, key=lambda item: item["label"])


def load_expected_costs(path: Path) -> dict[tuple[str, str], float]:
    expected = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            expected[(row["code_hash"], row["instance"])] = float(row["tour_cost"])
    return expected


def undirected_edges(route: np.ndarray) -> set[tuple[int, int]]:
    following = np.roll(route, -1)
    return {
        (min(int(left), int(right)), max(int(left), int(right)))
        for left, right in zip(route, following)
    }


def average_ranks(values: list[float]) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    position = 0
    while position < len(values):
        end = position + 1
        while end < len(values) and values[order[end]] == values[order[position]]:
            end += 1
        average = (position + 1 + end) / 2.0
        ranks[order[position:end]] = average
        position = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float:
    left_ranks = average_ranks(left)
    right_ranks = average_ranks(right)
    if np.std(left_ranks) == 0 or np.std(right_ranks) == 0:
        return 0.0
    return float(np.corrcoef(left_ranks, right_ranks)[0, 1])


def pairwise_similarity_rows(
    labels: list[str],
    instances: list[str],
    edges: dict[tuple[str, str], set[tuple[int, int]]],
    costs: dict[tuple[str, str], float],
) -> list[dict[str, Any]]:
    rows = []
    for left_label, right_label in itertools.combinations(labels, 2):
        jaccards = []
        identical = 0
        for instance in instances:
            left_edges = edges[(instance, left_label)]
            right_edges = edges[(instance, right_label)]
            jaccard = len(left_edges & right_edges) / len(left_edges | right_edges)
            jaccards.append(jaccard)
            identical += left_edges == right_edges
        rows.append(
            {
                "left_label": left_label,
                "right_label": right_label,
                "mean_edge_jaccard": statistics.fmean(jaccards),
                "median_edge_jaccard": statistics.median(jaccards),
                "min_edge_jaccard": min(jaccards),
                "max_edge_jaccard": max(jaccards),
                "identical_route_count": identical,
                "cost_spearman": spearman(
                    [costs[(instance, left_label)] for instance in instances],
                    [costs[(instance, right_label)] for instance in instances],
                ),
            }
        )
    return rows


def subset_value(mask: int, instance_costs: list[float]) -> float:
    if mask == 0:
        return 0.0
    selected = [cost for index, cost in enumerate(instance_costs) if mask & (1 << index)]
    baseline = max(instance_costs)
    return (baseline - min(selected)) / baseline * 100.0


def contribution_rows(
    labels: list[str],
    memberships: dict[str, str],
    instances: list[str],
    costs: dict[tuple[str, str], float],
) -> list[dict[str, Any]]:
    node_count = len(labels)
    shapley_totals = [0.0] * node_count
    unique_best = [0] * node_count
    best_including_ties = [0] * node_count
    leave_one_out = [[] for _ in labels]

    for instance in instances:
        instance_costs = [costs[(instance, label)] for label in labels]
        best_cost = min(instance_costs)
        best_indices = [index for index, cost in enumerate(instance_costs) if cost == best_cost]
        for index in best_indices:
            best_including_ties[index] += 1
        if len(best_indices) == 1:
            unique_best[best_indices[0]] += 1

        for index in range(node_count):
            without = min(cost for offset, cost in enumerate(instance_costs) if offset != index)
            leave_one_out[index].append((without / best_cost - 1.0) * 100.0)
            for mask in range(1 << node_count):
                if mask & (1 << index):
                    continue
                size = mask.bit_count()
                weight = (
                    math.factorial(size)
                    * math.factorial(node_count - size - 1)
                    / math.factorial(node_count)
                )
                shapley_totals[index] += weight * (
                    subset_value(mask | (1 << index), instance_costs)
                    - subset_value(mask, instance_costs)
                )

    rows = []
    for index, label in enumerate(labels):
        positive_loo = sum(value > 0 for value in leave_one_out[index])
        rows.append(
            {
                "label": label,
                "archive_membership": memberships[label],
                "best_count_including_ties": best_including_ties[index],
                "unique_best_count": unique_best[index],
                "positive_leave_one_out_instances": positive_loo,
                "mean_leave_one_out_regret_pct": statistics.fmean(leave_one_out[index]),
                "max_leave_one_out_regret_pct": max(leave_one_out[index]),
                "mean_shapley_improvement_pct": shapley_totals[index] / len(instances),
            }
        )
    return rows


def subset_score_rows(
    labels: list[str],
    instances: list[str],
    costs: dict[tuple[str, str], float],
) -> list[dict[str, Any]]:
    full_oracle = {instance: min(costs[(instance, label)] for label in labels) for instance in instances}
    rows = []
    for size in range(1, len(labels) + 1):
        for subset in itertools.combinations(labels, size):
            regrets = []
            for instance in instances:
                subset_best = min(costs[(instance, label)] for label in subset)
                regrets.append((subset_best / full_oracle[instance] - 1.0) * 100.0)
            rows.append(
                {
                    "subset_size": size,
                    "labels": "+".join(subset),
                    "mean_regret_pct": statistics.fmean(regrets),
                    "median_regret_pct": statistics.median(regrets),
                    "p90_regret_pct": float(np.percentile(regrets, 90)),
                    "max_regret_pct": max(regrets),
                    "exact_oracle_matches": sum(value == 0 for value in regrets),
                }
            )
    return rows


def best_frontier(subset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = []
    for size in sorted({int(row["subset_size"]) for row in subset_rows}):
        candidates = [row for row in subset_rows if int(row["subset_size"]) == size]
        frontier.append(
            min(
                candidates,
                key=lambda row: (
                    row["mean_regret_pct"],
                    row["p90_regret_pct"],
                    -row["exact_oracle_matches"],
                    row["labels"],
                ),
            )
        )
    return frontier


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有分析产物：{path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> None:
    load_plan(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "functional_diversity_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"禁止覆盖已有分析：{summary_path}")

    instance_entries = intervention.load_instances(args.instance_manifest)
    candidates = load_candidates(args.archive_metadata, args.code_catalog)
    expected = load_expected_costs(args.behavior_metrics)
    compiled = [(item, intervention.compile_heuristic(item["code"])) for item in candidates]
    labels = [item["label"] for item in candidates]
    memberships = {item["label"]: item["archive_membership"] for item in candidates}
    instances = [item["name"] for item in instance_entries]
    costs: dict[tuple[str, str], float] = {}
    edges: dict[tuple[str, str], set[tuple[int, int]]] = {}

    for item in instance_entries:
        instance = item["name"]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        for candidate, heuristic in compiled:
            route, cost = intervention.build_route(heuristic, distances)
            expected_cost = expected.get((candidate["code_hash"], instance))
            if expected_cost is None or cost != expected_cost:
                raise RuntimeError(
                    f"路线重放与 Stage BH 不一致：{instance} {candidate['label']} "
                    f"expected={expected_cost} actual={cost}"
                )
            costs[(instance, candidate["label"])] = cost
            edges[(instance, candidate["label"])] = undirected_edges(route)

    pairwise_rows = pairwise_similarity_rows(labels, instances, edges, costs)
    contribution = contribution_rows(labels, memberships, instances, costs)
    subset_rows = subset_score_rows(labels, instances, costs)
    frontier = best_frontier(subset_rows)
    pairwise_path = output_dir / "pairwise_route_similarity.csv"
    contribution_path = output_dir / "code_slot_contribution.csv"
    subsets_path = output_dir / "archive_subset_scores.csv"
    frontier_path = output_dir / "archive_coverage_frontier.csv"
    write_csv(pairwise_path, pairwise_rows)
    write_csv(contribution_path, contribution)
    write_csv(subsets_path, subset_rows)
    write_csv(frontier_path, frontier)

    pair_labels = set(("R2", "R4"))
    robust_labels = {"AW1", "AW2", "AW3", "AW4"}

    def group_mean(predicate: Any) -> float:
        values = [row["mean_edge_jaccard"] for row in pairwise_rows if predicate(row)]
        return statistics.fmean(values)

    summary = {
        "schema_version": "tsp-functional-route-diversity/v1",
        "analysis_plan_sha256": intervention.sha256_file(args.analysis_plan),
        "instance_count": len(instances),
        "code_count": len(labels),
        "route_coordinate_count": len(costs),
        "unique_route_coordinate_count": len(edges),
        "mean_edge_jaccard_by_group": {
            "fast_pair_internal": group_mean(
                lambda row: {row["left_label"], row["right_label"]} == pair_labels
            ),
            "robust_four_internal": group_mean(
                lambda row: row["left_label"] in robust_labels
                and row["right_label"] in robust_labels
            ),
            "cross_archive": group_mean(
                lambda row: (row["left_label"] in pair_labels)
                != (row["right_label"] in pair_labels)
            ),
        },
        "most_similar_pair": max(pairwise_rows, key=lambda row: row["mean_edge_jaccard"]),
        "least_similar_pair": min(pairwise_rows, key=lambda row: row["mean_edge_jaccard"]),
        "top_leave_one_out_code": max(
            contribution, key=lambda row: row["mean_leave_one_out_regret_pct"]
        ),
        "top_shapley_code": max(
            contribution, key=lambda row: row["mean_shapley_improvement_pct"]
        ),
        "frontier": frontier,
        "output_hashes": {
            "pairwise_route_similarity_sha256": intervention.sha256_file(pairwise_path),
            "code_slot_contribution_sha256": intervention.sha256_file(contribution_path),
            "archive_subset_scores_sha256": intervention.sha256_file(subsets_path),
            "archive_coverage_frontier_sha256": intervention.sha256_file(frontier_path),
        },
        "deployment_decision": "descriptive_only_no_archive_change",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-plan", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--behavior-metrics", type=Path, required=True)
    parser.add_argument("--archive-metadata", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
