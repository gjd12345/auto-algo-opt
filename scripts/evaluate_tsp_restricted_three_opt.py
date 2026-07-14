#!/usr/bin/env python3
"""在完整变邻域路线之上，测试受近邻约束的三边重连。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_iterated_nearest_two_opt as iterated
import evaluate_tsp_nearest_two_opt as nearest
import evaluate_tsp_or_opt_2_vnd as segment_move
import evaluate_tsp_relocation_vnd as relocation
import intervene_tsp_edge_variability as intervention


THREE_OPT_PATTERNS = (
    "reverse_b_reverse_c",
    "swap_b_c",
    "c_then_reverse_b",
    "reverse_c_then_b",
)

FIELDS = (
    "instance",
    "nodes",
    "winner_code_hash",
    "raw_baseline_cost",
    "stage_bz_cost",
    "stage_cb_cost",
    "restricted_three_opt_cost",
    "extra_vs_stage_cb_improvement_pct",
    "final_vs_raw_baseline_improvement_pct",
    "accepted_three_opt_count",
    "accepted_pattern_counts",
    "runtime_seconds",
    "feasible",
    "error_type",
)


def apply_three_opt(
    route: np.ndarray,
    first_edge: int,
    second_edge: int,
    third_edge: int,
    pattern: str,
) -> np.ndarray:
    """按固定四种真 3-opt 重连路线，并保持起点不变。"""
    if not 0 <= first_edge < second_edge < third_edge < len(route):
        raise ValueError("三条断边必须按路线位置严格递增")
    if second_edge <= first_edge + 1 or third_edge <= second_edge + 1:
        raise ValueError("相邻断边会退化为更小邻域")
    if pattern not in THREE_OPT_PATTERNS:
        raise ValueError(f"未知 3-opt 重连：{pattern}")

    prefix = route[: first_edge + 1]
    middle_b = route[first_edge + 1 : second_edge + 1]
    middle_c = route[second_edge + 1 : third_edge + 1]
    suffix = route[third_edge + 1 :]
    parts = {
        "reverse_b_reverse_c": (prefix, middle_b[::-1], middle_c[::-1], suffix),
        "swap_b_c": (prefix, middle_c, middle_b, suffix),
        "c_then_reverse_b": (prefix, middle_c, middle_b[::-1], suffix),
        "reverse_c_then_b": (prefix, middle_c[::-1], middle_b, suffix),
    }[pattern]
    return np.concatenate(parts)


def best_restricted_three_opt(
    route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    candidate_neighbor_count: int,
) -> tuple[np.ndarray, bool, str]:
    """只检查首条断边两端近邻附近的断边对，选择全局最佳重连。"""
    node_count = len(route)
    if node_count < 6:
        return route, False, ""
    if not 1 <= candidate_neighbor_count <= neighbors.shape[1]:
        raise ValueError("3-opt 近邻数超出已构建的近邻表")

    position_by_node = np.empty(node_count, dtype=np.int64)
    position_by_node[route] = np.arange(node_count, dtype=np.int64)
    best_delta = 0.0
    best_move: tuple[int, int, int, str] | None = None

    # 2-opt 和片段移位已收敛，只枚举会同时改变三条边的四种重连。
    for first_edge in range(node_count - 4):
        first_node = int(route[first_edge])
        second_node = int(route[first_edge + 1])
        candidate_nodes = np.concatenate(
            (
                neighbors[first_node, :candidate_neighbor_count],
                neighbors[second_node, :candidate_neighbor_count],
            )
        )
        candidate_positions = position_by_node[candidate_nodes]
        candidate_edges = np.unique(
            np.concatenate(
                (candidate_positions, (candidate_positions - 1) % node_count)
            )
        )
        candidate_edges = candidate_edges[candidate_edges >= first_edge + 2]
        if len(candidate_edges) < 2:
            continue

        second_indices, third_indices = np.triu_indices(len(candidate_edges), k=1)
        second_edges = candidate_edges[second_indices]
        third_edges = candidate_edges[third_indices]
        valid = third_edges >= second_edges + 2
        second_edges = second_edges[valid]
        third_edges = third_edges[valid]
        if len(second_edges) == 0:
            continue

        a = route[first_edge]
        b = route[first_edge + 1]
        c = route[second_edges]
        d = route[second_edges + 1]
        e = route[third_edges]
        f = route[(third_edges + 1) % node_count]
        removed = distances[a, b] + distances[c, d] + distances[e, f]
        deltas = (
            distances[a, c] + distances[b, e] + distances[d, f] - removed,
            distances[a, d] + distances[e, b] + distances[c, f] - removed,
            distances[a, d] + distances[e, c] + distances[b, f] - removed,
            distances[a, e] + distances[d, b] + distances[c, f] - removed,
        )
        for pattern_index, delta_values in enumerate(deltas):
            local_index = int(np.argmin(delta_values))
            local_delta = float(delta_values[local_index])
            # 相同降幅时保留更早的断边与重连类型，保证跨机器可重放。
            if local_delta < best_delta - 1e-12:
                best_delta = local_delta
                best_move = (
                    first_edge,
                    int(second_edges[local_index]),
                    int(third_edges[local_index]),
                    THREE_OPT_PATTERNS[pattern_index],
                )

    if best_move is None:
        return route, False, ""
    moved = apply_three_opt(route, *best_move)
    return moved, True, best_move[3]


def run_or_opt_3_vnd(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    stage_bz_search: dict[str, Any],
    stage_bw_search: dict[str, Any],
    stage_bv_search: dict[str, Any],
) -> np.ndarray:
    """重放 Stage BZ：三节点移动后依次收敛三个旧邻域。"""
    route = initial_route.copy()
    for _ in range(int(stage_bz_search["maximum_accepted_segment_moves"])):
        moved, improved = segment_move.best_segment_relocation(
            route,
            distances,
            neighbors,
            int(stage_bz_search["segment_length"]),
        )
        if not improved:
            break
        route, _ = nearest.nearest_two_opt(
            moved,
            distances,
            neighbors,
            int(stage_bz_search["two_opt_maximum_steps"]),
        )
        route, _, _, _ = relocation.run_vnd(
            route, distances, neighbors, stage_bv_search
        )
        route, _, _, _, _ = segment_move.run_or_opt_2_vnd(
            route, distances, neighbors, stage_bw_search, stage_bv_search
        )
    return route


def converge_full_vnd(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    stage_cb_search: dict[str, Any],
    stage_bz_search: dict[str, Any],
    stage_bw_search: dict[str, Any],
    stage_bv_search: dict[str, Any],
) -> np.ndarray:
    """按 Stage CB 冻结顺序，把四个旧邻域依次做到停止。"""
    route, _ = nearest.nearest_two_opt(
        initial_route,
        distances,
        neighbors,
        int(stage_cb_search["two_opt_maximum_steps"]),
    )
    route, _, _, _ = relocation.run_vnd(route, distances, neighbors, stage_bv_search)
    route, _, _, _, _ = segment_move.run_or_opt_2_vnd(
        route, distances, neighbors, stage_bw_search, stage_bv_search
    )
    return run_or_opt_3_vnd(
        route,
        distances,
        neighbors,
        stage_bz_search,
        stage_bw_search,
        stage_bv_search,
    )


def replay_stage_cb_route(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    instance: str,
    stage_cb_search: dict[str, Any],
    stage_bz_search: dict[str, Any],
    stage_bw_search: dict[str, Any],
    stage_bv_search: dict[str, Any],
) -> np.ndarray:
    """从 Stage BZ 路线重放确定性盆地重启，取严格更优路线。"""
    best_route = initial_route.copy()
    best_cost = intervention.route_cost(best_route, distances)
    role = str(stage_cb_search["deterministic_role"])
    for restart in stage_cb_search["restart_indices"]:
        perturbed = iterated.double_bridge(best_route, instance, role, int(restart))
        candidate = converge_full_vnd(
            perturbed,
            distances,
            neighbors,
            stage_cb_search,
            stage_bz_search,
            stage_bw_search,
            stage_bv_search,
        )
        candidate_cost = intervention.route_cost(candidate, distances)
        if candidate_cost < best_cost - 1e-12:
            best_route = candidate
            best_cost = candidate_cost
    return best_route


def run_restricted_three_opt(
    initial_route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    search: dict[str, Any],
    stage_cb_search: dict[str, Any],
    stage_bz_search: dict[str, Any],
    stage_bw_search: dict[str, Any],
    stage_bv_search: dict[str, Any],
) -> tuple[np.ndarray, Counter[str], float]:
    """每次接受真 3-opt 后重收敛旧邻域，直到没有严格改进。"""
    route = initial_route.copy()
    accepted_patterns: Counter[str] = Counter()
    started = time.perf_counter()
    for _ in range(int(search["maximum_accepted_three_opt_moves"])):
        moved, improved, pattern = best_restricted_three_opt(
            route,
            distances,
            neighbors,
            int(search["candidate_neighbor_count"]),
        )
        if not improved:
            break
        route = converge_full_vnd(
            moved,
            distances,
            neighbors,
            stage_cb_search,
            stage_bz_search,
            stage_bw_search,
            stage_bv_search,
        )
        accepted_patterns[pattern] += 1
    return route, accepted_patterns, time.perf_counter() - started


def load_protocol(args: argparse.Namespace) -> tuple[dict[str, Any], ...]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "stage_br_comparison_sha256": intervention.sha256_file(args.stage_br_comparison),
        "stage_bt_protocol_sha256": intervention.sha256_file(args.stage_bt_protocol),
        "stage_bt_results_sha256": intervention.sha256_file(args.stage_bt_results),
        "stage_bv_protocol_sha256": intervention.sha256_file(args.stage_bv_protocol),
        "stage_bv_results_sha256": intervention.sha256_file(args.stage_bv_results),
        "stage_bw_protocol_sha256": intervention.sha256_file(args.stage_bw_protocol),
        "stage_bw_results_sha256": intervention.sha256_file(args.stage_bw_results),
        "stage_bz_protocol_sha256": intervention.sha256_file(args.stage_bz_protocol),
        "stage_bz_results_sha256": intervention.sha256_file(args.stage_bz_results),
        "stage_cb_protocol_sha256": intervention.sha256_file(args.stage_cb_protocol),
        "stage_cb_results_sha256": intervention.sha256_file(args.stage_cb_results),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return (
        protocol,
        json.loads(args.stage_bt_protocol.read_text(encoding="utf-8")),
        json.loads(args.stage_bv_protocol.read_text(encoding="utf-8")),
        json.loads(args.stage_bw_protocol.read_text(encoding="utf-8")),
        json.loads(args.stage_bz_protocol.read_text(encoding="utf-8")),
        json.loads(args.stage_cb_protocol.read_text(encoding="utf-8")),
    )


def summarize(rows: list[dict[str, str]], protocol: dict[str, Any]) -> dict[str, Any]:
    extras = [float(row["extra_vs_stage_cb_improvement_pct"]) for row in rows]
    finals = [float(row["final_vs_raw_baseline_improvement_pct"]) for row in rows]
    valid_count = sum(row["feasible"] == "True" for row in rows)
    metrics = {
        "valid_result_count": valid_count,
        "nonworse_than_stage_cb_instances": sum(value >= 0 for value in extras),
        "strictly_better_than_stage_cb_instances": sum(value > 0 for value in extras),
        "mean_extra_improvement_pct": statistics.fmean(extras),
        "median_extra_improvement_pct": statistics.median(extras),
        "max_extra_improvement_pct": max(extras),
        "final_mean_improvement_pct": statistics.fmean(finals),
        "final_median_improvement_pct": statistics.median(finals),
        "final_max_improvement_pct": max(finals),
        "accepted_three_opt_count": sum(
            int(row["accepted_three_opt_count"]) for row in rows
        ),
        "median_runtime_seconds": statistics.median(
            float(row["runtime_seconds"]) for row in rows
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "valid_results": valid_count >= gate["valid_result_count_min"],
        "nonworse": metrics["nonworse_than_stage_cb_instances"]
        >= gate["nonworse_than_stage_cb_instances_min"],
        "strictly_better": metrics["strictly_better_than_stage_cb_instances"]
        >= gate["strictly_better_than_stage_cb_instances_min"],
        "median_extra": metrics["median_extra_improvement_pct"]
        >= gate["median_extra_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-restricted-three-opt-summary/v1",
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
    (
        protocol,
        stage_bt_protocol,
        stage_bv_protocol,
        stage_bw_protocol,
        stage_bz_protocol,
        stage_cb_protocol,
    ) = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "restricted_three_opt_results.csv"
    summary_path = output_dir / "restricted_three_opt_summary.json"
    if result_path.exists() or summary_path.exists():
        raise FileExistsError("受限 3-opt 输出已存在，禁止覆盖或重复坐标")

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
    stage_bw_rows = {
        (row["instance"], row["archive_role"]): row
        for row in relocation.load_csv(args.stage_bw_results)
    }
    stage_bz_rows = {
        row["instance"]: row for row in relocation.load_csv(args.stage_bz_results)
    }
    stage_cb_rows = {
        row["instance"]: row for row in relocation.load_csv(args.stage_cb_results)
    }
    instances = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }
    winner_hashes = {
        instance: row["portfolio_winner"] for instance, row in comparisons.items()
    }
    codes = relocation.load_codes(args.code_catalog, set(winner_hashes.values()))
    compiled = {
        code_hash: intervention.compile_heuristic(code)
        for code_hash, code in codes.items()
    }

    rows: list[dict[str, Any]] = []
    for instance, item in instances.items():
        comparison = comparisons[instance]
        winner_hash = winner_hashes[instance]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        neighbors = nearest.build_nearest_neighbors(
            distances,
            int(protocol["search"]["nearest_neighbor_count"]),
            int(protocol["search"]["neighbor_build_block_size"]),
        )
        raw_baseline_cost = float(comparison["baseline_cost"])
        try:
            raw_route, raw_portfolio_cost = intervention.build_route(
                compiled[winner_hash], distances
            )
            if raw_portfolio_cost != float(comparison["portfolio_cost"]):
                raise RuntimeError("Stage BR 组合赢家重放成本不一致")
            stage_bt_outcome = iterated.run_search(
                raw_route,
                distances,
                neighbors,
                instance,
                "portfolio",
                stage_bt_protocol["search"],
            )
            stage_bt_route = stage_bt_outcome["best_route"]
            if intervention.route_cost(stage_bt_route, distances) != float(
                stage_bt_rows[(instance, "portfolio")]["ils_cost"]
            ):
                raise RuntimeError("Stage BT 重放成本不一致")
            stage_bv_route, _, _, _ = relocation.run_vnd(
                stage_bt_route, distances, neighbors, stage_bv_protocol["search"]
            )
            if intervention.route_cost(stage_bv_route, distances) != float(
                stage_bv_rows[(instance, "portfolio")]["vnd_cost"]
            ):
                raise RuntimeError("Stage BV 重放成本不一致")
            stage_bw_route, _, _, _, _ = segment_move.run_or_opt_2_vnd(
                stage_bv_route,
                distances,
                neighbors,
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            if intervention.route_cost(stage_bw_route, distances) != float(
                stage_bw_rows[(instance, "portfolio")]["or_opt_2_cost"]
            ):
                raise RuntimeError("Stage BW 重放成本不一致")
            stage_bz_route = run_or_opt_3_vnd(
                stage_bw_route,
                distances,
                neighbors,
                stage_bz_protocol["search"],
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            stage_bz_cost = intervention.route_cost(stage_bz_route, distances)
            if stage_bz_cost != float(stage_bz_rows[instance]["or_opt_3_cost"]):
                raise RuntimeError("Stage BZ 重放成本不一致")
            stage_cb_route = replay_stage_cb_route(
                stage_bz_route,
                distances,
                neighbors,
                instance,
                stage_cb_protocol["search"],
                stage_bz_protocol["search"],
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            stage_cb_cost = intervention.route_cost(stage_cb_route, distances)
            if stage_cb_cost != float(stage_cb_rows[instance]["restart_best_cost"]):
                raise RuntimeError("Stage CB 重放成本不一致")
            final_route, patterns, runtime = run_restricted_three_opt(
                stage_cb_route,
                distances,
                neighbors,
                protocol["search"],
                stage_cb_protocol["search"],
                stage_bz_protocol["search"],
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            final_cost = intervention.route_cost(final_route, distances)
            row = {
                "instance": instance,
                "nodes": len(coords),
                "winner_code_hash": winner_hash,
                "raw_baseline_cost": raw_baseline_cost,
                "stage_bz_cost": stage_bz_cost,
                "stage_cb_cost": stage_cb_cost,
                "restricted_three_opt_cost": final_cost,
                "extra_vs_stage_cb_improvement_pct": relocation.improvement(
                    stage_cb_cost, final_cost
                ),
                "final_vs_raw_baseline_improvement_pct": relocation.improvement(
                    raw_baseline_cost, final_cost
                ),
                "accepted_three_opt_count": sum(patterns.values()),
                "accepted_pattern_counts": json.dumps(
                    dict(patterns), ensure_ascii=False, sort_keys=True
                ),
                "runtime_seconds": runtime,
                "feasible": True,
                "error_type": "",
            }
        except Exception as exc:  # 失败坐标必须保留，不能换实例掩盖错误。
            row = {
                "instance": instance,
                "nodes": len(coords),
                "winner_code_hash": winner_hash,
                "raw_baseline_cost": raw_baseline_cost,
                "stage_bz_cost": stage_bz_rows[instance]["or_opt_3_cost"],
                "stage_cb_cost": stage_cb_rows[instance]["restart_best_cost"],
                "restricted_three_opt_cost": "",
                "extra_vs_stage_cb_improvement_pct": "",
                "final_vs_raw_baseline_improvement_pct": "",
                "accepted_three_opt_count": "",
                "accepted_pattern_counts": "",
                "runtime_seconds": "",
                "feasible": False,
                "error_type": type(exc).__name__,
            }
        rows.append(row)
        with result_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()

    if len(rows) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("受限 3-opt 结果不完整")
    if any(not row["feasible"] for row in rows):
        raise RuntimeError("受限 3-opt 存在失败坐标，禁止生成成功摘要")
    summary = summarize(
        [{key: str(value) for key, value in row.items()} for row in rows], protocol
    )
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
    parser.add_argument("--stage-bw-protocol", type=Path, required=True)
    parser.add_argument("--stage-bw-results", type=Path, required=True)
    parser.add_argument("--stage-bz-protocol", type=Path, required=True)
    parser.add_argument("--stage-bz-results", type=Path, required=True)
    parser.add_argument("--stage-cb-protocol", type=Path, required=True)
    parser.add_argument("--stage-cb-results", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
