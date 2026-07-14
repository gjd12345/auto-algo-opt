#!/usr/bin/env python3
"""用冻结的几何近邻 2-opt 修复四槽与质量组合路线。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import intervene_tsp_edge_variability as intervention
import select_tsp_quality_portfolio as quality


FIELDS = (
    "instance",
    "nodes",
    "baseline_winner",
    "portfolio_winner",
    "raw_baseline_cost",
    "raw_portfolio_cost",
    "raw_portfolio_improvement_pct",
    "repaired_baseline_cost",
    "repaired_portfolio_cost",
    "baseline_repair_extra_improvement_pct",
    "portfolio_repair_extra_improvement_pct",
    "repaired_portfolio_vs_repaired_baseline_improvement_pct",
    "final_vs_raw_baseline_improvement_pct",
    "baseline_repair_steps",
    "portfolio_repair_steps",
    "baseline_route_runtime_seconds",
    "portfolio_route_runtime_seconds",
    "neighbor_build_runtime_seconds",
    "baseline_repair_runtime_seconds",
    "portfolio_repair_runtime_seconds",
)


def load_protocol(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    common_checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "split_manifest_sha256": intervention.sha256_file(args.split_manifest),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in common_checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    portfolio = json.loads(args.frozen_portfolio.read_text(encoding="utf-8"))
    return protocol, portfolio


def load_codes(catalog_path: Path, required_hashes: list[str]) -> dict[str, str]:
    codes = {}
    with catalog_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if item["code_hash"] in required_hashes:
                    codes[item["code_hash"]] = item["code"]
    if set(codes) != set(required_hashes):
        raise ValueError("冻结组合代码在历史目录中不完整")
    for code_hash, code in codes.items():
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash:
            raise RuntimeError(f"源码 hash 不匹配：{code_hash}")
    return codes


def build_nearest_neighbors(
    distances: np.ndarray,
    neighbor_count: int,
    block_size: int,
) -> np.ndarray:
    """分块寻找几何近邻，避免一次生成 n×n 的索引副本。"""
    node_count = len(distances)
    count = min(neighbor_count, node_count - 1)
    neighbors = np.empty((node_count, count), dtype=np.int64)
    for start in range(0, node_count, block_size):
        end = min(start + block_size, node_count)
        block = distances[start:end]
        partial = np.argpartition(block, kth=count, axis=1)[:, : count + 1]
        for offset, candidate_nodes in enumerate(partial):
            node = start + offset
            filtered = [int(item) for item in candidate_nodes if int(item) != node]
            # 距离并列时按节点编号固定顺序，保证不同运行得到同一邻域。
            filtered.sort(key=lambda item: (float(distances[node, item]), item))
            neighbors[node] = filtered[:count]
    return neighbors


def nearest_two_opt(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    maximum_steps: int,
) -> tuple[np.ndarray, int]:
    """每步检查近邻诱导的边交换，只接受全局最佳的严格降成本移动。"""
    route = initial_route.copy()
    node_count = len(route)
    neighbor_count = neighbors.shape[1]
    route_positions = np.arange(node_count, dtype=np.int64)
    for step in range(maximum_steps):
        position_by_node = np.empty(node_count, dtype=np.int64)
        position_by_node[route] = route_positions
        first_positions = np.repeat(route_positions, neighbor_count)
        neighbor_nodes = neighbors[route].reshape(-1)
        second_positions = position_by_node[neighbor_nodes]
        left = np.minimum(first_positions, second_positions)
        right = np.maximum(first_positions, second_positions)
        valid = (right - left > 1) & ~((left == 0) & (right == node_count - 1))
        pair_ids = np.unique(left[valid] * node_count + right[valid])
        left = pair_ids // node_count
        right = pair_ids % node_count

        a = route[left]
        b = route[(left + 1) % node_count]
        c = route[right]
        d = route[(right + 1) % node_count]
        delta = distances[a, c] + distances[b, d] - distances[a, b] - distances[c, d]
        best_index = int(np.argmin(delta))
        if float(delta[best_index]) >= -1e-12:
            return route, step
        route = intervention.apply_two_opt(
            route, int(left[best_index]), int(right[best_index])
        )
    return route, maximum_steps


def load_existing(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    if not path.exists():
        return [], set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    instances = {row["instance"] for row in rows}
    if len(instances) != len(rows):
        raise ValueError(f"检查点存在重复实例：{path}")
    return rows, instances


def append_row(path: Path, row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def improvement(reference: float, candidate: float) -> float:
    return (reference - candidate) / reference * 100.0


def summarize(rows: list[dict[str, str]], gate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool]]:
    portfolio_extra = [float(row["portfolio_repair_extra_improvement_pct"]) for row in rows]
    repaired_gap = [
        float(row["repaired_portfolio_vs_repaired_baseline_improvement_pct"])
        for row in rows
    ]
    final = [float(row["final_vs_raw_baseline_improvement_pct"]) for row in rows]
    metrics = {
        "instance_count": len(rows),
        "valid_route_count": len(rows) * 2,
        "portfolio_repair_improved_instances": sum(value > 0 for value in portfolio_extra),
        "portfolio_repair_mean_extra_improvement_pct": statistics.fmean(portfolio_extra),
        "portfolio_repair_median_extra_improvement_pct": statistics.median(portfolio_extra),
        "portfolio_repair_max_extra_improvement_pct": max(portfolio_extra),
        "repaired_portfolio_vs_repaired_baseline_wins": sum(value > 0 for value in repaired_gap),
        "repaired_portfolio_vs_repaired_baseline_same": sum(value == 0 for value in repaired_gap),
        "repaired_portfolio_vs_repaired_baseline_losses": sum(value < 0 for value in repaired_gap),
        "repaired_portfolio_vs_repaired_baseline_mean_improvement_pct": statistics.fmean(
            repaired_gap
        ),
        "repaired_portfolio_vs_repaired_baseline_median_improvement_pct": statistics.median(
            repaired_gap
        ),
        "final_vs_raw_baseline_mean_improvement_pct": statistics.fmean(final),
        "final_vs_raw_baseline_median_improvement_pct": statistics.median(final),
        "final_vs_raw_baseline_max_improvement_pct": max(final),
        "median_portfolio_repair_runtime_seconds": statistics.median(
            float(row["portfolio_repair_runtime_seconds"]) for row in rows
        ),
    }
    checks = {
        "valid_routes": metrics["valid_route_count"] >= gate["valid_route_count_min"],
        "portfolio_improved_instances": metrics["portfolio_repair_improved_instances"]
        >= gate["portfolio_repair_improved_instances_min"],
        "portfolio_extra_median": metrics["portfolio_repair_median_extra_improvement_pct"]
        >= gate["portfolio_repair_median_extra_improvement_pct_min"],
        "matched_wins": metrics["repaired_portfolio_vs_repaired_baseline_wins"]
        >= gate["repaired_portfolio_vs_repaired_baseline_wins_min"],
        "matched_losses": metrics["repaired_portfolio_vs_repaired_baseline_losses"]
        <= gate["repaired_portfolio_vs_repaired_baseline_losses_max"],
        "final_mean": metrics["final_vs_raw_baseline_mean_improvement_pct"]
        >= gate["final_vs_raw_baseline_mean_improvement_pct_min"],
    }
    return metrics, checks


def run_phase(args: argparse.Namespace, protocol: dict[str, Any], portfolio: dict[str, Any]) -> None:
    split_name = "discovery" if args.phase == "discover" else "confirmation"
    expected_hash = protocol["inputs"][f"{split_name}_results_sha256"]
    if intervention.sha256_file(args.code_results) != expected_hash:
        raise RuntimeError(f"{split_name} 结果 hash 不匹配")
    if args.phase == "confirm":
        if intervention.sha256_file(args.frozen_discovery) != args.expected_discovery_sha256:
            raise RuntimeError("冻结发现摘要 hash 不匹配")
        frozen = json.loads(args.frozen_discovery.read_text(encoding="utf-8"))
        if not frozen["discovery_passed"]:
            raise RuntimeError("发现门槛未通过，禁止运行确认阶段")

    instances = quality.load_split(args.split_manifest, split_name)
    code_rows, by_coordinate = quality.load_results(
        args.code_results,
        expected_hash,
        instances,
        expected_code_count=99,
    )
    baseline_hashes = portfolio["baseline_code_hashes"]
    portfolio_hashes = portfolio["portfolio_code_hashes"]
    baseline_costs, baseline_winners = quality.best_costs(
        instances, baseline_hashes, by_coordinate
    )
    portfolio_costs, portfolio_winners = quality.best_costs(
        instances, portfolio_hashes, by_coordinate
    )
    codes = load_codes(args.code_catalog, portfolio_hashes)
    compiled = {
        code_hash: intervention.compile_heuristic(code) for code_hash, code in codes.items()
    }
    instance_manifest = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{split_name}_nearest_two_opt.csv"
    summary_path = output_dir / f"{split_name}_nearest_two_opt_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"{split_name} 阶段已完成：{summary_path}")
    _, completed = load_existing(result_path)
    repair = protocol["repair"]
    for instance in instances:
        if instance in completed:
            continue
        item = instance_manifest[instance]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        started = time.perf_counter()
        neighbors = build_nearest_neighbors(
            distances,
            int(repair["nearest_neighbor_count"]),
            int(repair["neighbor_build_block_size"]),
        )
        neighbor_runtime = time.perf_counter() - started

        routes = {}
        route_runtimes = {}
        for role, winner_hash, expected_cost in (
            ("baseline", baseline_winners[instance], baseline_costs[instance]),
            ("portfolio", portfolio_winners[instance], portfolio_costs[instance]),
        ):
            if winner_hash not in routes:
                started = time.perf_counter()
                route, cost = intervention.build_route(compiled[winner_hash], distances)
                route_runtimes[winner_hash] = time.perf_counter() - started
                if cost != expected_cost:
                    raise RuntimeError(
                        f"原路线成本与 Stage BQ 不一致：{instance} {role} {cost} != {expected_cost}"
                    )
                routes[winner_hash] = route

        baseline_route = routes[baseline_winners[instance]]
        portfolio_route = routes[portfolio_winners[instance]]
        started = time.perf_counter()
        repaired_baseline, baseline_steps = nearest_two_opt(
            baseline_route,
            distances,
            neighbors,
            int(repair["maximum_steps"]),
        )
        baseline_repair_runtime = time.perf_counter() - started
        started = time.perf_counter()
        repaired_portfolio, portfolio_steps = nearest_two_opt(
            portfolio_route,
            distances,
            neighbors,
            int(repair["maximum_steps"]),
        )
        portfolio_repair_runtime = time.perf_counter() - started
        repaired_baseline_cost = intervention.route_cost(repaired_baseline, distances)
        repaired_portfolio_cost = intervention.route_cost(repaired_portfolio, distances)
        row = {
            "instance": instance,
            "nodes": len(coords),
            "baseline_winner": baseline_winners[instance],
            "portfolio_winner": portfolio_winners[instance],
            "raw_baseline_cost": baseline_costs[instance],
            "raw_portfolio_cost": portfolio_costs[instance],
            "raw_portfolio_improvement_pct": improvement(
                baseline_costs[instance], portfolio_costs[instance]
            ),
            "repaired_baseline_cost": repaired_baseline_cost,
            "repaired_portfolio_cost": repaired_portfolio_cost,
            "baseline_repair_extra_improvement_pct": improvement(
                baseline_costs[instance], repaired_baseline_cost
            ),
            "portfolio_repair_extra_improvement_pct": improvement(
                portfolio_costs[instance], repaired_portfolio_cost
            ),
            "repaired_portfolio_vs_repaired_baseline_improvement_pct": improvement(
                repaired_baseline_cost, repaired_portfolio_cost
            ),
            "final_vs_raw_baseline_improvement_pct": improvement(
                baseline_costs[instance], repaired_portfolio_cost
            ),
            "baseline_repair_steps": baseline_steps,
            "portfolio_repair_steps": portfolio_steps,
            "baseline_route_runtime_seconds": route_runtimes[baseline_winners[instance]],
            "portfolio_route_runtime_seconds": route_runtimes[portfolio_winners[instance]],
            "neighbor_build_runtime_seconds": neighbor_runtime,
            "baseline_repair_runtime_seconds": baseline_repair_runtime,
            "portfolio_repair_runtime_seconds": portfolio_repair_runtime,
        }
        append_row(result_path, row)

    rows, completed = load_existing(result_path)
    if len(completed) != len(instances):
        raise RuntimeError(f"{split_name} 修复结果不完整")
    gate = protocol[f"{split_name}_gate"]
    metrics, checks = summarize(rows, gate)
    passed = all(checks.values())
    summary = {
        "schema_version": f"tsp-nearest-two-opt-{split_name}-summary/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "code_results_sha256": intervention.sha256_file(args.code_results),
        "result_sha256": intervention.sha256_file(result_path),
        "metrics": metrics,
        "checks": checks,
        "decision": protocol["decision"][
            f"{split_name}_{'pass' if passed else 'fail'}"
        ],
        "default_pool_behavior": "unchanged",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.phase == "discover":
        frozen_path = output_dir / "frozen_repair_discovery.json"
        frozen = {
            "schema_version": "tsp-nearest-two-opt-frozen-discovery/v1",
            "protocol_sha256": intervention.sha256_file(args.protocol),
            "discovery_summary_sha256": intervention.sha256_file(summary_path),
            "discovery_result_sha256": intervention.sha256_file(result_path),
            "confirmation_results_sha256": protocol["inputs"]["confirmation_results_sha256"],
            "discovery_passed": passed,
            "repair": repair,
            "confirmation_results_read": False,
        }
        frozen_path.write_text(
            json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(summary, ensure_ascii=False, indent=2)
            + f"\nFROZEN_DISCOVERY_SHA256={intervention.sha256_file(frozen_path)}"
        )
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("discover", "confirm"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--code-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frozen-discovery", type=Path)
    parser.add_argument("--expected-discovery-sha256")
    args = parser.parse_args()
    if args.phase == "confirm" and (
        args.frozen_discovery is None or not args.expected_discovery_sha256
    ):
        parser.error("confirm 必须提供冻结发现摘要及其预期 hash")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    frozen_protocol, frozen_portfolio = load_protocol(parsed)
    run_phase(parsed, frozen_protocol, frozen_portfolio)
