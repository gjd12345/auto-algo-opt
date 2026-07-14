#!/usr/bin/env python3
"""在高规模 TSP 路线上评估确定性双桥扰动与近邻 2-opt 再收敛。"""

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
import evaluate_tsp_nearest_two_opt as nearest
import intervene_tsp_edge_variability as intervention


FIELDS = (
    "instance",
    "nodes",
    "archive_role",
    "winner_code_hash",
    "raw_cost",
    "nearest100_cost",
    "converged_cost",
    "ils_cost",
    "nearest100_extra_improvement_pct",
    "convergence_extra_improvement_pct",
    "ils_extra_vs_nearest100_improvement_pct",
    "ils_extra_vs_converged_improvement_pct",
    "nearest100_steps",
    "convergence_extra_steps",
    "accepted_restart_count",
    "winner_route_runtime_seconds",
    "neighbor_build_runtime_seconds",
    "total_search_runtime_seconds",
    "feasible",
    "error_type",
)


def load_protocol(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "stage_br_code_results_sha256": intervention.sha256_file(args.stage_br_code_results),
        "stage_br_comparison_sha256": intervention.sha256_file(args.stage_br_comparison),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    portfolio = json.loads(args.frozen_portfolio.read_text(encoding="utf-8"))
    return protocol, portfolio


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


def double_bridge(route: np.ndarray, instance: str, role: str, restart: int) -> np.ndarray:
    """从四个路段各取一个切点，交换第二与第四段，形成确定性强扰动。"""
    node_count = len(route)
    quarter = node_count // 4
    rng = np.random.default_rng(
        intervention.deterministic_seed(f"{instance}:{role}:{restart}")
    )
    first = int(rng.integers(1, quarter))
    second = int(rng.integers(quarter, 2 * quarter))
    third = int(rng.integers(2 * quarter, 3 * quarter))
    fourth = int(rng.integers(3 * quarter, node_count - 1))
    return np.concatenate(
        (
            route[:first],
            route[third:fourth],
            route[second:third],
            route[first:second],
            route[fourth:],
        )
    )


def improvement(reference: float, candidate: float) -> float:
    return (reference - candidate) / reference * 100.0


def run_search(
    route: np.ndarray,
    distances: np.ndarray,
    neighbors: np.ndarray,
    instance: str,
    role: str,
    search: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    route100, steps100 = nearest.nearest_two_opt(
        route,
        distances,
        neighbors,
        int(search["stage_bs_reference_steps"]),
    )
    remaining_steps = int(search["local_convergence_maximum_steps"]) - steps100
    converged, extra_steps = nearest.nearest_two_opt(
        route100,
        distances,
        neighbors,
        max(remaining_steps, 0),
    )
    best_route = converged
    best_cost = intervention.route_cost(best_route, distances)
    accepted_restarts = 0
    for restart in range(int(search["restart_count"])):
        perturbed = double_bridge(best_route, instance, role, restart)
        candidate, _ = nearest.nearest_two_opt(
            perturbed,
            distances,
            neighbors,
            int(search["local_convergence_maximum_steps"]),
        )
        candidate_cost = intervention.route_cost(candidate, distances)
        if candidate_cost < best_cost - 1e-12:
            best_route = candidate
            best_cost = candidate_cost
            accepted_restarts += 1
    return {
        "route100": route100,
        "converged": converged,
        "best_route": best_route,
        "steps100": steps100,
        "extra_steps": extra_steps,
        "accepted_restarts": accepted_restarts,
        "runtime": time.perf_counter() - started,
    }


def load_existing(path: Path) -> tuple[list[dict[str, str]], set[tuple[str, str]]]:
    if not path.exists():
        return [], set()
    rows = load_csv(path)
    keys = {(row["instance"], row["archive_role"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("迭代搜索检查点存在重复")
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
            improvement(float(portfolio["nearest100_cost"]), float(portfolio["ils_cost"]))
        )
        matched.append(
            improvement(float(baseline["ils_cost"]), float(portfolio["ils_cost"]))
        )
        final.append(
            improvement(float(baseline["raw_cost"]), float(portfolio["ils_cost"]))
        )
    valid_count = sum(row["feasible"] == "True" for row in rows)
    metrics = {
        "instance_count": len(grouped),
        "valid_result_count": valid_count,
        "portfolio_ils_nonworse_than_nearest100_instances": sum(
            value >= 0 for value in portfolio_extra
        ),
        "portfolio_ils_strictly_better_than_nearest100_instances": sum(
            value > 0 for value in portfolio_extra
        ),
        "portfolio_ils_mean_extra_improvement_pct": statistics.fmean(portfolio_extra),
        "portfolio_ils_median_extra_improvement_pct": statistics.median(portfolio_extra),
        "ils_portfolio_vs_ils_baseline_wins": sum(value > 0 for value in matched),
        "ils_portfolio_vs_ils_baseline_same": sum(value == 0 for value in matched),
        "ils_portfolio_vs_ils_baseline_losses": sum(value < 0 for value in matched),
        "ils_portfolio_vs_ils_baseline_mean_improvement_pct": statistics.fmean(matched),
        "ils_portfolio_vs_ils_baseline_median_improvement_pct": statistics.median(matched),
        "final_portfolio_vs_raw_baseline_mean_improvement_pct": statistics.fmean(final),
        "final_portfolio_vs_raw_baseline_median_improvement_pct": statistics.median(final),
        "final_portfolio_vs_raw_baseline_max_improvement_pct": max(final),
        "median_portfolio_total_search_runtime_seconds": statistics.median(
            float(row["total_search_runtime_seconds"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
        "portfolio_accepted_restart_count": sum(
            int(row["accepted_restart_count"])
            for row in rows
            if row["archive_role"] == "portfolio"
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "valid_results": valid_count >= gate["valid_result_count_min"],
        "portfolio_nonworse": metrics["portfolio_ils_nonworse_than_nearest100_instances"]
        >= gate["portfolio_ils_nonworse_than_nearest100_instances_min"],
        "portfolio_strictly_better": metrics[
            "portfolio_ils_strictly_better_than_nearest100_instances"
        ]
        >= gate["portfolio_ils_strictly_better_than_nearest100_instances_min"],
        "portfolio_extra_median": metrics["portfolio_ils_median_extra_improvement_pct"]
        >= gate["portfolio_ils_median_extra_improvement_pct_min"],
        "matched_wins": metrics["ils_portfolio_vs_ils_baseline_wins"]
        >= gate["ils_portfolio_vs_ils_baseline_wins_min"],
        "matched_losses": metrics["ils_portfolio_vs_ils_baseline_losses"]
        <= gate["ils_portfolio_vs_ils_baseline_losses_max"],
        "final_median": metrics["final_portfolio_vs_raw_baseline_median_improvement_pct"]
        >= gate["final_portfolio_vs_raw_baseline_median_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-deterministic-iterated-nearest-two-opt-summary/v1",
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
    protocol, portfolio = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "iterated_nearest_two_opt_results.csv"
    summary_path = output_dir / "iterated_nearest_two_opt_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"迭代局部搜索已完成：{summary_path}")

    comparisons = {row["instance"]: row for row in load_csv(args.stage_br_comparison)}
    expected_instances = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }
    if set(comparisons) != set(expected_instances):
        raise ValueError("Stage BR 比较与高规模实例不一致")
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
    for instance, item in expected_instances.items():
        pending_roles = [
            role for role in ("baseline", "portfolio") if (instance, role) not in completed
        ]
        if not pending_roles:
            continue
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        started = time.perf_counter()
        neighbors = nearest.build_nearest_neighbors(
            distances,
            int(search["nearest_neighbor_count"]),
            int(search["neighbor_build_block_size"]),
        )
        neighbor_runtime = time.perf_counter() - started
        for role in pending_roles:
            winner_hash = winner_by_key[(instance, role)]
            started = time.perf_counter()
            try:
                route, raw_cost = intervention.build_route(compiled[winner_hash], distances)
                route_runtime = time.perf_counter() - started
                expected_cost = raw_cost_by_key[(instance, role)]
                if raw_cost != expected_cost:
                    raise RuntimeError(
                        f"原路线成本与 Stage BR 不一致：{instance} {role}"
                    )
                outcome = run_search(
                    route, distances, neighbors, instance, role, search
                )
                nearest100_cost = intervention.route_cost(outcome["route100"], distances)
                converged_cost = intervention.route_cost(outcome["converged"], distances)
                ils_cost = intervention.route_cost(outcome["best_route"], distances)
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost,
                    "nearest100_cost": nearest100_cost,
                    "converged_cost": converged_cost,
                    "ils_cost": ils_cost,
                    "nearest100_extra_improvement_pct": improvement(raw_cost, nearest100_cost),
                    "convergence_extra_improvement_pct": improvement(
                        nearest100_cost, converged_cost
                    ),
                    "ils_extra_vs_nearest100_improvement_pct": improvement(
                        nearest100_cost, ils_cost
                    ),
                    "ils_extra_vs_converged_improvement_pct": improvement(
                        converged_cost, ils_cost
                    ),
                    "nearest100_steps": outcome["steps100"],
                    "convergence_extra_steps": outcome["extra_steps"],
                    "accepted_restart_count": outcome["accepted_restarts"],
                    "winner_route_runtime_seconds": route_runtime,
                    "neighbor_build_runtime_seconds": neighbor_runtime,
                    "total_search_runtime_seconds": outcome["runtime"],
                    "feasible": True,
                    "error_type": "",
                }
            except Exception as exc:  # 高规模失败保留坐标，不替换实例或搜索参数。
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost_by_key[(instance, role)],
                    "nearest100_cost": "",
                    "converged_cost": "",
                    "ils_cost": "",
                    "nearest100_extra_improvement_pct": "",
                    "convergence_extra_improvement_pct": "",
                    "ils_extra_vs_nearest100_improvement_pct": "",
                    "ils_extra_vs_converged_improvement_pct": "",
                    "nearest100_steps": "",
                    "convergence_extra_steps": "",
                    "accepted_restart_count": "",
                    "winner_route_runtime_seconds": time.perf_counter() - started,
                    "neighbor_build_runtime_seconds": neighbor_runtime,
                    "total_search_runtime_seconds": "",
                    "feasible": False,
                    "error_type": type(exc).__name__,
                }
            append_row(result_path, row)
            completed.add((instance, role))

    rows, completed = load_existing(result_path)
    if len(completed) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("迭代局部搜索结果不完整")
    if any(row["feasible"] != "True" for row in rows):
        raise RuntimeError("迭代局部搜索存在失败坐标，禁止生成成功摘要")
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
    parser.add_argument("--stage-br-code-results", type=Path, required=True)
    parser.add_argument("--stage-br-comparison", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
