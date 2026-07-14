#!/usr/bin/env python3
"""在 Stage BT 路线上交替执行单节点移位与近邻 2-opt 收敛。"""

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
import evaluate_tsp_iterated_nearest_two_opt as iterated
import evaluate_tsp_nearest_two_opt as nearest
import intervene_tsp_edge_variability as intervention


FIELDS = (
    "instance",
    "nodes",
    "archive_role",
    "winner_code_hash",
    "raw_cost",
    "stage_bt_cost",
    "vnd_cost",
    "vnd_extra_vs_stage_bt_improvement_pct",
    "final_vs_raw_improvement_pct",
    "accepted_relocation_count",
    "two_opt_step_count_after_relocations",
    "vnd_runtime_seconds",
    "feasible",
    "error_type",
)


def load_protocol(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "stage_br_comparison_sha256": intervention.sha256_file(args.stage_br_comparison),
        "stage_bt_protocol_sha256": intervention.sha256_file(args.stage_bt_protocol),
        "stage_bt_results_sha256": intervention.sha256_file(args.stage_bt_results),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    stage_bt_protocol = json.loads(args.stage_bt_protocol.read_text(encoding="utf-8"))
    portfolio = json.loads(args.frozen_portfolio.read_text(encoding="utf-8"))
    return protocol, stage_bt_protocol, portfolio


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_codes(catalog_path: Path, required_hashes: set[str]) -> dict[str, str]:
    codes = {}
    with catalog_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if item["code_hash"] in required_hashes:
                    codes[item["code_hash"]] = item["code"]
    if set(codes) != required_hashes:
        raise ValueError("高规模胜出代码在历史目录中不完整")
    for code_hash, code in codes.items():
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash:
            raise RuntimeError(f"源码 hash 不匹配：{code_hash}")
    return codes


def apply_relocation(route: np.ndarray, source: int, edge_start: int) -> np.ndarray:
    """移除 source 位置节点，再把它插到原 edge_start 边之后。"""
    node = route[source]
    reduced = np.delete(route, source)
    insert_at = edge_start if source < edge_start else edge_start + 1
    return np.insert(reduced, insert_at, node)


def best_relocation(
    route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """枚举近邻前后插入位置，选择全局最佳的严格降成本移位。"""
    node_count = len(route)
    neighbor_count = neighbors.shape[1]
    positions = np.arange(node_count, dtype=np.int64)
    position_by_node = np.empty(node_count, dtype=np.int64)
    position_by_node[route] = positions
    source = np.repeat(positions[1:], neighbor_count * 2)
    neighbor_nodes = neighbors[route[1:]].reshape(-1)
    neighbor_positions = position_by_node[neighbor_nodes]
    after_edges = neighbor_positions
    before_edges = (neighbor_positions - 1) % node_count
    edge_start = np.column_stack((after_edges, before_edges)).reshape(-1)

    invalid_previous = (source - 1) % node_count
    valid = (edge_start != source) & (edge_start != invalid_previous)
    pair_ids = np.unique(source[valid] * node_count + edge_start[valid])
    source = pair_ids // node_count
    edge_start = pair_ids % node_count

    previous_node = route[(source - 1) % node_count]
    moved_node = route[source]
    next_node = route[(source + 1) % node_count]
    insertion_left = route[edge_start]
    insertion_right = route[(edge_start + 1) % node_count]
    delta = (
        distances[previous_node, next_node]
        + distances[insertion_left, moved_node]
        + distances[moved_node, insertion_right]
        - distances[previous_node, moved_node]
        - distances[moved_node, next_node]
        - distances[insertion_left, insertion_right]
    )
    best_index = int(np.argmin(delta))
    if float(delta[best_index]) >= -1e-12:
        return route, False
    return (
        apply_relocation(route, int(source[best_index]), int(edge_start[best_index])),
        True,
    )


def run_vnd(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    search: dict[str, Any],
) -> tuple[np.ndarray, int, int, float]:
    route = initial_route.copy()
    accepted = 0
    two_opt_steps = 0
    started = time.perf_counter()
    for _ in range(int(search["maximum_accepted_relocations"])):
        relocated, improved = best_relocation(route, distances, neighbors)
        if not improved:
            break
        route, steps = nearest.nearest_two_opt(
            relocated,
            distances,
            neighbors,
            int(search["two_opt_maximum_steps_after_each_relocation"]),
        )
        accepted += 1
        two_opt_steps += steps
    return route, accepted, two_opt_steps, time.perf_counter() - started


def improvement(reference: float, candidate: float) -> float:
    return (reference - candidate) / reference * 100.0


def load_existing(path: Path) -> tuple[list[dict[str, str]], set[tuple[str, str]]]:
    if not path.exists():
        return [], set()
    rows = load_csv(path)
    keys = {(row["instance"], row["archive_role"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("变邻域检查点存在重复")
    return rows, keys


def append_row(path: Path, row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def summarize(rows: list[dict[str, str]], protocol: dict[str, Any]) -> dict[str, Any]:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["instance"], {})[row["archive_role"]] = row
    portfolio_extra = []
    matched = []
    final = []
    for roles in grouped.values():
        baseline = roles["baseline"]
        portfolio = roles["portfolio"]
        portfolio_extra.append(
            improvement(float(portfolio["stage_bt_cost"]), float(portfolio["vnd_cost"]))
        )
        matched.append(
            improvement(float(baseline["vnd_cost"]), float(portfolio["vnd_cost"]))
        )
        final.append(
            improvement(float(baseline["raw_cost"]), float(portfolio["vnd_cost"]))
        )
    valid_count = sum(row["feasible"] == "True" for row in rows)
    metrics = {
        "instance_count": len(grouped),
        "valid_result_count": valid_count,
        "portfolio_vnd_nonworse_than_stage_bt_instances": sum(
            value >= 0 for value in portfolio_extra
        ),
        "portfolio_vnd_strictly_better_than_stage_bt_instances": sum(
            value > 0 for value in portfolio_extra
        ),
        "portfolio_vnd_mean_extra_improvement_pct": statistics.fmean(portfolio_extra),
        "portfolio_vnd_median_extra_improvement_pct": statistics.median(portfolio_extra),
        "vnd_portfolio_vs_vnd_baseline_wins": sum(value > 0 for value in matched),
        "vnd_portfolio_vs_vnd_baseline_same": sum(value == 0 for value in matched),
        "vnd_portfolio_vs_vnd_baseline_losses": sum(value < 0 for value in matched),
        "vnd_portfolio_vs_vnd_baseline_mean_improvement_pct": statistics.fmean(matched),
        "vnd_portfolio_vs_vnd_baseline_median_improvement_pct": statistics.median(matched),
        "final_portfolio_vs_raw_baseline_mean_improvement_pct": statistics.fmean(final),
        "final_portfolio_vs_raw_baseline_median_improvement_pct": statistics.median(final),
        "final_portfolio_vs_raw_baseline_max_improvement_pct": max(final),
        "portfolio_accepted_relocation_count": sum(
            int(row["accepted_relocation_count"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
        "median_portfolio_vnd_runtime_seconds": statistics.median(
            float(row["vnd_runtime_seconds"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "valid_results": valid_count >= gate["valid_result_count_min"],
        "portfolio_nonworse": metrics["portfolio_vnd_nonworse_than_stage_bt_instances"]
        >= gate["portfolio_vnd_nonworse_than_stage_bt_instances_min"],
        "portfolio_strictly_better": metrics[
            "portfolio_vnd_strictly_better_than_stage_bt_instances"
        ]
        >= gate["portfolio_vnd_strictly_better_than_stage_bt_instances_min"],
        "portfolio_extra_median": metrics["portfolio_vnd_median_extra_improvement_pct"]
        >= gate["portfolio_vnd_median_extra_improvement_pct_min"],
        "matched_wins": metrics["vnd_portfolio_vs_vnd_baseline_wins"]
        >= gate["vnd_portfolio_vs_vnd_baseline_wins_min"],
        "matched_losses": metrics["vnd_portfolio_vs_vnd_baseline_losses"]
        <= gate["vnd_portfolio_vs_vnd_baseline_losses_max"],
        "final_median": metrics["final_portfolio_vs_raw_baseline_median_improvement_pct"]
        >= gate["final_portfolio_vs_raw_baseline_median_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-single-node-relocation-vnd-summary/v1",
        "metrics": metrics,
        "checks": checks,
        "decision": (
            protocol["decision"]["all_checks_pass"]
            if all(checks.values())
            else protocol["decision"]["otherwise"]
        ),
        "default_pool_behavior": "unchanged",
    }


def run(args: argparse.Namespace) -> None:
    protocol, stage_bt_protocol, _ = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "relocation_vnd_results.csv"
    summary_path = output_dir / "relocation_vnd_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"变邻域搜索已完成：{summary_path}")

    comparisons = {row["instance"]: row for row in load_csv(args.stage_br_comparison)}
    stage_bt_rows = {
        (row["instance"], row["archive_role"]): row
        for row in load_csv(args.stage_bt_results)
    }
    instances = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }
    winner_by_key = {}
    raw_cost_by_key = {}
    for instance, row in comparisons.items():
        winner_by_key[(instance, "baseline")] = row["baseline_winner"]
        winner_by_key[(instance, "portfolio")] = row["portfolio_winner"]
        raw_cost_by_key[(instance, "baseline")] = float(row["baseline_cost"])
        raw_cost_by_key[(instance, "portfolio")] = float(row["portfolio_cost"])
    required_hashes = set(winner_by_key.values())
    codes = load_codes(args.code_catalog, required_hashes)
    compiled = {
        code_hash: intervention.compile_heuristic(code) for code_hash, code in codes.items()
    }
    _, completed = load_existing(result_path)
    search = protocol["search"]
    stage_bt_search = stage_bt_protocol["search"]
    for instance, item in instances.items():
        pending_roles = [
            role for role in ("baseline", "portfolio") if (instance, role) not in completed
        ]
        if not pending_roles:
            continue
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        neighbors = nearest.build_nearest_neighbors(
            distances,
            int(search["nearest_neighbor_count"]),
            int(search["neighbor_build_block_size"]),
        )
        for role in pending_roles:
            winner_hash = winner_by_key[(instance, role)]
            try:
                route, raw_cost = intervention.build_route(compiled[winner_hash], distances)
                if raw_cost != raw_cost_by_key[(instance, role)]:
                    raise RuntimeError("原路线成本与 Stage BR 不一致")
                stage_bt_outcome = iterated.run_search(
                    route,
                    distances,
                    neighbors,
                    instance,
                    role,
                    stage_bt_search,
                )
                stage_bt_route = stage_bt_outcome["best_route"]
                stage_bt_cost = intervention.route_cost(stage_bt_route, distances)
                expected_stage_bt_cost = float(stage_bt_rows[(instance, role)]["ils_cost"])
                if stage_bt_cost != expected_stage_bt_cost:
                    raise RuntimeError("重放成本与 Stage BT 不一致")
                vnd_route, relocations, two_opt_steps, runtime = run_vnd(
                    stage_bt_route, distances, neighbors, search
                )
                vnd_cost = intervention.route_cost(vnd_route, distances)
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost,
                    "stage_bt_cost": stage_bt_cost,
                    "vnd_cost": vnd_cost,
                    "vnd_extra_vs_stage_bt_improvement_pct": improvement(
                        stage_bt_cost, vnd_cost
                    ),
                    "final_vs_raw_improvement_pct": improvement(raw_cost, vnd_cost),
                    "accepted_relocation_count": relocations,
                    "two_opt_step_count_after_relocations": two_opt_steps,
                    "vnd_runtime_seconds": runtime,
                    "feasible": True,
                    "error_type": "",
                }
            except Exception as exc:  # 失败留痕，不事后缩小邻域或替换实例。
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost_by_key[(instance, role)],
                    "stage_bt_cost": stage_bt_rows[(instance, role)]["ils_cost"],
                    "vnd_cost": "",
                    "vnd_extra_vs_stage_bt_improvement_pct": "",
                    "final_vs_raw_improvement_pct": "",
                    "accepted_relocation_count": "",
                    "two_opt_step_count_after_relocations": "",
                    "vnd_runtime_seconds": "",
                    "feasible": False,
                    "error_type": type(exc).__name__,
                }
            append_row(result_path, row)
            completed.add((instance, role))

    rows, completed = load_existing(result_path)
    if len(completed) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("变邻域结果不完整")
    if any(row["feasible"] != "True" for row in rows):
        raise RuntimeError("变邻域存在失败坐标，禁止生成成功摘要")
    summary = summarize(rows, protocol)
    summary.update(
        {
            "protocol_sha256": intervention.sha256_file(args.protocol),
            "result_sha256": intervention.sha256_file(result_path),
        }
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--stage-br-comparison", type=Path, required=True)
    parser.add_argument("--stage-bt-protocol", type=Path, required=True)
    parser.add_argument("--stage-bt-results", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
