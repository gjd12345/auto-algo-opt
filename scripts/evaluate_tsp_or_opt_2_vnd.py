#!/usr/bin/env python3
"""在单节点移位收敛路线之上，测试连续两节点整体移位。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_iterated_nearest_two_opt as iterated
import evaluate_tsp_nearest_two_opt as nearest
import evaluate_tsp_relocation_vnd as relocation
import intervene_tsp_edge_variability as intervention


FIELDS = (
    "instance",
    "nodes",
    "archive_role",
    "winner_code_hash",
    "raw_cost",
    "stage_bv_cost",
    "or_opt_2_cost",
    "extra_vs_stage_bv_improvement_pct",
    "final_vs_raw_improvement_pct",
    "accepted_or_opt_2_count",
    "followup_relocation_count",
    "followup_two_opt_step_count",
    "or_opt_2_runtime_seconds",
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
        "stage_bv_protocol_sha256": intervention.sha256_file(args.stage_bv_protocol),
        "stage_bv_results_sha256": intervention.sha256_file(args.stage_bv_results),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    stage_bt_protocol = json.loads(args.stage_bt_protocol.read_text(encoding="utf-8"))
    stage_bv_protocol = json.loads(args.stage_bv_protocol.read_text(encoding="utf-8"))
    return protocol, stage_bt_protocol, stage_bv_protocol


def apply_segment_relocation(
    route: np.ndarray,
    source: int,
    edge_start: int,
    segment_length: int,
) -> np.ndarray:
    """移除一段连续节点，再保持内部顺序插到指定边之后。"""
    segment = route[source : source + segment_length]
    removed_positions = np.arange(source, source + segment_length)
    reduced = np.delete(route, removed_positions)
    # 原插入边位于片段之后时，删除片段会让该边整体左移。
    insert_at = (
        edge_start - segment_length + 1
        if source < edge_start
        else edge_start + 1
    )
    return np.insert(reduced, insert_at, segment)


def best_segment_relocation(
    route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    segment_length: int,
) -> tuple[np.ndarray, bool]:
    """枚举片段首尾近邻附近的插入边，选择全局最佳严格改进。"""
    node_count = len(route)
    if segment_length < 2 or segment_length > node_count - 2:
        raise ValueError("连续片段长度必须在 2 到 n-2 之间")
    neighbor_count = neighbors.shape[1]
    source_positions = np.arange(
        1, node_count - segment_length + 1, dtype=np.int64
    )
    position_by_node = np.empty(node_count, dtype=np.int64)
    position_by_node[route] = np.arange(node_count, dtype=np.int64)

    first_nodes = route[source_positions]
    last_nodes = route[source_positions + segment_length - 1]
    # 同时观察片段首尾节点的近邻，避免只照顾片段的一端。
    candidate_nodes = np.concatenate(
        (neighbors[first_nodes], neighbors[last_nodes]), axis=1
    )
    candidate_positions = position_by_node[candidate_nodes]
    edge_start = np.stack(
        (candidate_positions, (candidate_positions - 1) % node_count), axis=2
    ).reshape(-1)
    source = np.repeat(source_positions, neighbor_count * 4)

    # 片段内部边和片段前一条边都不能作为插入位置，否则只是原地重放。
    valid = (edge_start < source - 1) | (
        edge_start > source + segment_length - 1
    )
    pair_ids = np.unique(source[valid] * node_count + edge_start[valid])
    source = pair_ids // node_count
    edge_start = pair_ids % node_count

    previous_node = route[source - 1]
    first_node = route[source]
    last_node = route[source + segment_length - 1]
    next_node = route[(source + segment_length) % node_count]
    insertion_left = route[edge_start]
    insertion_right = route[(edge_start + 1) % node_count]
    delta = (
        distances[previous_node, next_node]
        + distances[insertion_left, first_node]
        + distances[last_node, insertion_right]
        - distances[previous_node, first_node]
        - distances[last_node, next_node]
        - distances[insertion_left, insertion_right]
    )
    best_index = int(np.argmin(delta))
    if float(delta[best_index]) >= -1e-12:
        return route, False
    return (
        apply_segment_relocation(
            route,
            int(source[best_index]),
            int(edge_start[best_index]),
            segment_length,
        ),
        True,
    )


def apply_or_opt_2(route: np.ndarray, source: int, edge_start: int) -> np.ndarray:
    """保留旧入口，确保已冻结的 Or-opt-2 实验可精确重放。"""
    return apply_segment_relocation(route, source, edge_start, segment_length=2)


def best_or_opt_2(
    route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """保留旧入口，使用长度为 2 的通用连续片段邻域。"""
    return best_segment_relocation(route, distances, neighbors, segment_length=2)


def run_or_opt_2_vnd(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    search: dict[str, Any],
    relocation_search: dict[str, Any],
) -> tuple[np.ndarray, int, int, int, float]:
    """交替执行两节点移位、2-opt 和单节点移位，直到新邻域停止。"""
    route = initial_route.copy()
    accepted = 0
    relocation_count = 0
    two_opt_steps = 0
    started = time.perf_counter()
    for _ in range(int(search["maximum_accepted_or_opt_2_moves"])):
        moved, improved = best_or_opt_2(route, distances, neighbors)
        if not improved:
            break
        route, steps = nearest.nearest_two_opt(
            moved,
            distances,
            neighbors,
            int(search["two_opt_maximum_steps_after_each_or_opt_2"]),
        )
        route, relocations, followup_steps, _ = relocation.run_vnd(
            route, distances, neighbors, relocation_search
        )
        accepted += 1
        relocation_count += relocations
        two_opt_steps += steps + followup_steps
    return route, accepted, relocation_count, two_opt_steps, time.perf_counter() - started


def load_existing(path: Path) -> tuple[list[dict[str, str]], set[tuple[str, str]]]:
    if not path.exists():
        return [], set()
    rows = relocation.load_csv(path)
    keys = {(row["instance"], row["archive_role"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("Or-opt-2 检查点存在重复")
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
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["instance"], {})[row["archive_role"]] = row
    portfolio_extra = []
    matched = []
    final = []
    for roles in grouped.values():
        baseline = roles["baseline"]
        portfolio = roles["portfolio"]
        portfolio_extra.append(
            relocation.improvement(
                float(portfolio["stage_bv_cost"]), float(portfolio["or_opt_2_cost"])
            )
        )
        matched.append(
            relocation.improvement(
                float(baseline["or_opt_2_cost"]), float(portfolio["or_opt_2_cost"])
            )
        )
        final.append(
            relocation.improvement(
                float(baseline["raw_cost"]), float(portfolio["or_opt_2_cost"])
            )
        )
    valid_count = sum(row["feasible"] == "True" for row in rows)
    metrics = {
        "instance_count": len(grouped),
        "valid_result_count": valid_count,
        "portfolio_nonworse_than_stage_bv_instances": sum(v >= 0 for v in portfolio_extra),
        "portfolio_strictly_better_than_stage_bv_instances": sum(
            v > 0 for v in portfolio_extra
        ),
        "portfolio_mean_extra_improvement_pct": statistics.fmean(portfolio_extra),
        "portfolio_median_extra_improvement_pct": statistics.median(portfolio_extra),
        "portfolio_vs_baseline_wins": sum(v > 0 for v in matched),
        "portfolio_vs_baseline_same": sum(v == 0 for v in matched),
        "portfolio_vs_baseline_losses": sum(v < 0 for v in matched),
        "portfolio_vs_baseline_mean_improvement_pct": statistics.fmean(matched),
        "portfolio_vs_baseline_median_improvement_pct": statistics.median(matched),
        "final_portfolio_vs_raw_baseline_mean_improvement_pct": statistics.fmean(final),
        "final_portfolio_vs_raw_baseline_median_improvement_pct": statistics.median(final),
        "final_portfolio_vs_raw_baseline_max_improvement_pct": max(final),
        "portfolio_accepted_or_opt_2_count": sum(
            int(row["accepted_or_opt_2_count"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
        "median_portfolio_runtime_seconds": statistics.median(
            float(row["or_opt_2_runtime_seconds"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "valid_results": valid_count >= gate["valid_result_count_min"],
        "portfolio_nonworse": metrics["portfolio_nonworse_than_stage_bv_instances"]
        >= gate["portfolio_nonworse_than_stage_bv_instances_min"],
        "portfolio_strictly_better": metrics[
            "portfolio_strictly_better_than_stage_bv_instances"
        ]
        >= gate["portfolio_strictly_better_than_stage_bv_instances_min"],
        "portfolio_extra_median": metrics["portfolio_median_extra_improvement_pct"]
        >= gate["portfolio_median_extra_improvement_pct_min"],
        "matched_wins": metrics["portfolio_vs_baseline_wins"]
        >= gate["portfolio_vs_baseline_wins_min"],
        "matched_losses": metrics["portfolio_vs_baseline_losses"]
        <= gate["portfolio_vs_baseline_losses_max"],
        "final_median": metrics["final_portfolio_vs_raw_baseline_median_improvement_pct"]
        >= gate["final_portfolio_vs_raw_baseline_median_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-or-opt-2-vnd-summary/v1",
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
    protocol, stage_bt_protocol, stage_bv_protocol = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "or_opt_2_vnd_results.csv"
    summary_path = output_dir / "or_opt_2_vnd_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"Or-opt-2 已完成：{summary_path}")

    comparisons = {
        row["instance"]: row for row in relocation.load_csv(args.stage_br_comparison)
    }
    stage_bt_rows = {
        (row["instance"], row["archive_role"]): row
        for row in relocation.load_csv(args.stage_bt_results)
    }
    stage_bv_rows = {
        (row["instance"], row["archive_role"]): row
        for row in relocation.load_csv(args.stage_bv_results)
    }
    instances = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }
    winner_by_key: dict[tuple[str, str], str] = {}
    raw_cost_by_key: dict[tuple[str, str], float] = {}
    for instance, row in comparisons.items():
        for role, column in (("baseline", "baseline_winner"), ("portfolio", "portfolio_winner")):
            winner_by_key[(instance, role)] = row[column]
            raw_cost_by_key[(instance, role)] = float(row[f"{role}_cost"])
    required_hashes = set(winner_by_key.values())
    codes = relocation.load_codes(args.code_catalog, required_hashes)
    compiled = {
        code_hash: intervention.compile_heuristic(code) for code_hash, code in codes.items()
    }
    _, completed = load_existing(result_path)
    search = protocol["search"]
    stage_bt_search = stage_bt_protocol["search"]
    stage_bv_search = stage_bv_protocol["search"]
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
            key = (instance, role)
            winner_hash = winner_by_key[key]
            try:
                route, raw_cost = intervention.build_route(compiled[winner_hash], distances)
                if raw_cost != raw_cost_by_key[key]:
                    raise RuntimeError("原路线成本与 Stage BR 不一致")
                stage_bt_outcome = iterated.run_search(
                    route, distances, neighbors, instance, role, stage_bt_search
                )
                stage_bt_route = stage_bt_outcome["best_route"]
                if intervention.route_cost(stage_bt_route, distances) != float(
                    stage_bt_rows[key]["ils_cost"]
                ):
                    raise RuntimeError("Stage BT 重放成本不一致")
                stage_bv_route, _, _, _ = relocation.run_vnd(
                    stage_bt_route, distances, neighbors, stage_bv_search
                )
                stage_bv_cost = intervention.route_cost(stage_bv_route, distances)
                if stage_bv_cost != float(stage_bv_rows[key]["vnd_cost"]):
                    raise RuntimeError("Stage BV 重放成本不一致")
                final_route, moves, relocations, two_opt_steps, runtime = run_or_opt_2_vnd(
                    stage_bv_route, distances, neighbors, search, stage_bv_search
                )
                final_cost = intervention.route_cost(final_route, distances)
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost,
                    "stage_bv_cost": stage_bv_cost,
                    "or_opt_2_cost": final_cost,
                    "extra_vs_stage_bv_improvement_pct": relocation.improvement(
                        stage_bv_cost, final_cost
                    ),
                    "final_vs_raw_improvement_pct": relocation.improvement(
                        raw_cost, final_cost
                    ),
                    "accepted_or_opt_2_count": moves,
                    "followup_relocation_count": relocations,
                    "followup_two_opt_step_count": two_opt_steps,
                    "or_opt_2_runtime_seconds": runtime,
                    "feasible": True,
                    "error_type": "",
                }
            except Exception as exc:  # 固定坐标失败时保留记录，禁止事后换实例。
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost_by_key[key],
                    "stage_bv_cost": stage_bv_rows[key]["vnd_cost"],
                    "or_opt_2_cost": "",
                    "extra_vs_stage_bv_improvement_pct": "",
                    "final_vs_raw_improvement_pct": "",
                    "accepted_or_opt_2_count": "",
                    "followup_relocation_count": "",
                    "followup_two_opt_step_count": "",
                    "or_opt_2_runtime_seconds": "",
                    "feasible": False,
                    "error_type": type(exc).__name__,
                }
            append_row(result_path, row)
            completed.add(key)

    rows, completed = load_existing(result_path)
    if len(completed) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("Or-opt-2 结果不完整")
    if any(row["feasible"] != "True" for row in rows):
        raise RuntimeError("Or-opt-2 存在失败坐标，禁止生成成功摘要")
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
    parser.add_argument("--stage-bv-protocol", type=Path, required=True)
    parser.add_argument("--stage-bv-results", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
