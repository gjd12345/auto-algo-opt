#!/usr/bin/env python3
"""在高规模官方实例上确认冻结 TSP 质量组合及固定局部修复。"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import intervene_tsp_edge_variability as intervention


CODE_FIELDS = (
    "instance",
    "nodes",
    "code_hash",
    "archive_role",
    "tour_cost",
    "runtime_seconds",
    "route_hash",
    "feasible",
    "error_type",
)

COMPARISON_FIELDS = (
    "instance",
    "nodes",
    "baseline_winner",
    "portfolio_winner",
    "portfolio_winner_is_addition",
    "baseline_cost",
    "portfolio_cost",
    "raw_portfolio_improvement_pct",
    "repaired_baseline_cost",
    "repaired_portfolio_cost",
    "repaired_portfolio_improvement_pct",
    "repaired_portfolio_vs_raw_baseline_improvement_pct",
    "baseline_repair_extra_improvement_pct",
    "portfolio_repair_extra_improvement_pct",
    "baseline_repair_steps",
    "portfolio_repair_steps",
    "baseline_archive_runtime_seconds",
    "portfolio_archive_runtime_seconds",
    "baseline_repair_runtime_seconds",
    "portfolio_repair_runtime_seconds",
)


def load_protocol(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
        "stage_bq_confirmation_summary_sha256": intervention.sha256_file(
            args.stage_bq_confirmation_summary
        ),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    portfolio = json.loads(args.frozen_portfolio.read_text(encoding="utf-8"))
    return protocol, portfolio


def load_candidates(
    catalog_path: Path,
    baseline_hashes: list[str],
    addition_hashes: list[str],
) -> list[dict[str, Any]]:
    required = baseline_hashes + addition_hashes
    catalog = {}
    with catalog_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if item["code_hash"] in required:
                    catalog[item["code_hash"]] = item
    if set(catalog) != set(required) or len(required) != len(set(required)):
        raise ValueError("冻结组合与代码目录不一致")
    candidates = []
    for code_hash in required:
        code = catalog[code_hash]["code"]
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash:
            raise RuntimeError(f"源码 hash 不匹配：{code_hash}")
        candidates.append(
            {
                "code_hash": code_hash,
                "code": code,
                "archive_role": "baseline" if code_hash in baseline_hashes else "addition",
            }
        )
    return candidates


def load_existing(path: Path, key_field: str) -> tuple[list[dict[str, str]], set[Any]]:
    if not path.exists():
        return [], set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if key_field == "coordinate":
        keys = {(row["instance"], row["code_hash"]) for row in rows}
    else:
        keys = {row[key_field] for row in rows}
    if len(keys) != len(rows):
        raise ValueError(f"检查点存在重复：{path}")
    return rows, keys


def append_row(path: Path, fields: tuple[str, ...], row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def improvement(reference: float, candidate: float) -> float:
    return (reference - candidate) / reference * 100.0


def build_comparison(
    instance: str,
    distances: np.ndarray,
    routes: dict[str, np.ndarray],
    runtimes: dict[str, float],
    baseline_hashes: list[str],
    portfolio_hashes: list[str],
    repair: dict[str, Any],
) -> dict[str, Any]:
    def winner(code_hashes: list[str]) -> str:
        return min(
            code_hashes,
            key=lambda code_hash: (
                intervention.route_cost(routes[code_hash], distances),
                code_hash,
            ),
        )

    baseline_winner = winner(baseline_hashes)
    portfolio_winner = winner(portfolio_hashes)
    baseline_route = routes[baseline_winner]
    portfolio_route = routes[portfolio_winner]
    baseline_cost = intervention.route_cost(baseline_route, distances)
    portfolio_cost = intervention.route_cost(portfolio_route, distances)

    repair_args = (
        0,
        int(repair["maximum_steps"]),
        int(repair["candidate_pairs_per_step"]),
    )
    started = time.perf_counter()
    repaired_baseline, baseline_steps = intervention.run_arm(
        baseline_route,
        distances,
        instance,
        "cost_best_positive_control",
        *repair_args,
    )
    baseline_repair_runtime = time.perf_counter() - started
    started = time.perf_counter()
    repaired_portfolio, portfolio_steps = intervention.run_arm(
        portfolio_route,
        distances,
        instance,
        "cost_best_positive_control",
        *repair_args,
    )
    portfolio_repair_runtime = time.perf_counter() - started
    repaired_baseline_cost = intervention.route_cost(repaired_baseline, distances)
    repaired_portfolio_cost = intervention.route_cost(repaired_portfolio, distances)
    return {
        "instance": instance,
        "nodes": len(distances),
        "baseline_winner": baseline_winner,
        "portfolio_winner": portfolio_winner,
        "portfolio_winner_is_addition": portfolio_winner not in baseline_hashes,
        "baseline_cost": baseline_cost,
        "portfolio_cost": portfolio_cost,
        "raw_portfolio_improvement_pct": improvement(baseline_cost, portfolio_cost),
        "repaired_baseline_cost": repaired_baseline_cost,
        "repaired_portfolio_cost": repaired_portfolio_cost,
        "repaired_portfolio_improvement_pct": improvement(
            repaired_baseline_cost, repaired_portfolio_cost
        ),
        "repaired_portfolio_vs_raw_baseline_improvement_pct": improvement(
            baseline_cost, repaired_portfolio_cost
        ),
        "baseline_repair_extra_improvement_pct": improvement(
            baseline_cost, repaired_baseline_cost
        ),
        "portfolio_repair_extra_improvement_pct": improvement(
            portfolio_cost, repaired_portfolio_cost
        ),
        "baseline_repair_steps": baseline_steps,
        "portfolio_repair_steps": portfolio_steps,
        "baseline_archive_runtime_seconds": sum(runtimes[item] for item in baseline_hashes),
        "portfolio_archive_runtime_seconds": sum(runtimes[item] for item in portfolio_hashes),
        "baseline_repair_runtime_seconds": baseline_repair_runtime,
        "portfolio_repair_runtime_seconds": portfolio_repair_runtime,
    }


def summarize(
    protocol: dict[str, Any],
    code_rows: list[dict[str, str]],
    comparisons: list[dict[str, str]],
) -> dict[str, Any]:
    raw = [float(row["raw_portfolio_improvement_pct"]) for row in comparisons]
    repaired = [float(row["repaired_portfolio_improvement_pct"]) for row in comparisons]
    final = [
        float(row["repaired_portfolio_vs_raw_baseline_improvement_pct"])
        for row in comparisons
    ]
    valid_count = sum(row["feasible"] == "True" for row in code_rows)
    metrics = {
        "instance_count": len(comparisons),
        "feasible_code_coordinate_count": valid_count,
        "raw_portfolio_wins": sum(value > 0 for value in raw),
        "raw_portfolio_same": sum(value == 0 for value in raw),
        "raw_portfolio_losses": sum(value < 0 for value in raw),
        "raw_portfolio_mean_improvement_pct": statistics.fmean(raw),
        "raw_portfolio_median_improvement_pct": statistics.median(raw),
        "raw_portfolio_max_improvement_pct": max(raw),
        "repaired_portfolio_wins": sum(value > 0 for value in repaired),
        "repaired_portfolio_same": sum(value == 0 for value in repaired),
        "repaired_portfolio_losses": sum(value < 0 for value in repaired),
        "repaired_portfolio_mean_improvement_pct": statistics.fmean(repaired),
        "repaired_portfolio_median_improvement_pct": statistics.median(repaired),
        "repaired_portfolio_max_improvement_pct": max(repaired),
        "repaired_portfolio_vs_raw_baseline_mean_improvement_pct": statistics.fmean(final),
        "repaired_portfolio_vs_raw_baseline_median_improvement_pct": statistics.median(final),
        "portfolio_repair_median_extra_improvement_pct": statistics.median(
            float(row["portfolio_repair_extra_improvement_pct"]) for row in comparisons
        ),
        "median_portfolio_archive_runtime_seconds": statistics.median(
            float(row["portfolio_archive_runtime_seconds"]) for row in comparisons
        ),
        "max_portfolio_archive_runtime_seconds": max(
            float(row["portfolio_archive_runtime_seconds"]) for row in comparisons
        ),
        "median_portfolio_repair_runtime_seconds": statistics.median(
            float(row["portfolio_repair_runtime_seconds"]) for row in comparisons
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "feasible_coordinates": valid_count >= gate["feasible_code_coordinates_min"],
        "raw_wins": metrics["raw_portfolio_wins"] >= gate["raw_portfolio_wins_min"],
        "raw_losses": metrics["raw_portfolio_losses"] <= gate["raw_portfolio_losses_max"],
        "raw_median": metrics["raw_portfolio_median_improvement_pct"]
        >= gate["raw_portfolio_median_improvement_pct_min"],
        "repaired_wins": metrics["repaired_portfolio_wins"]
        >= gate["repaired_portfolio_wins_min"],
        "repaired_losses": metrics["repaired_portfolio_losses"]
        <= gate["repaired_portfolio_losses_max"],
        "repaired_median": metrics["repaired_portfolio_median_improvement_pct"]
        >= gate["repaired_portfolio_median_improvement_pct_min"],
        "final_median": metrics["repaired_portfolio_vs_raw_baseline_median_improvement_pct"]
        >= gate["repaired_portfolio_vs_raw_baseline_median_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-quality-portfolio-high-scale-repair-summary/v1",
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
    summary_path = output_dir / "high_scale_quality_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"高规模确认已完成：{summary_path}")

    baseline_hashes = portfolio["baseline_code_hashes"]
    addition_hashes = portfolio["selected_addition_code_hashes"]
    portfolio_hashes = baseline_hashes + addition_hashes
    candidates = load_candidates(args.code_catalog, baseline_hashes, addition_hashes)
    if len(candidates) != int(protocol["archives"]["expected_total_code_count"]):
        raise ValueError("冻结组合代码数不一致")
    compiled = {
        item["code_hash"]: intervention.compile_heuristic(item["code"])
        for item in candidates
    }

    code_path = output_dir / "high_scale_quality_code_results.csv"
    comparison_path = output_dir / "high_scale_quality_comparison.csv"
    _, code_keys = load_existing(code_path, "coordinate")
    _, comparison_instances = load_existing(comparison_path, "instance")
    for instance_item in intervention.load_instances(args.instance_manifest):
        instance = instance_item["name"]
        coords = np.asarray(
            behavior.load_tsp(Path(instance_item["path"]))["coords"], dtype=float
        )
        distances = intervention.build_distance_matrix(coords)
        routes = {}
        runtimes = {}
        for candidate in candidates:
            code_hash = candidate["code_hash"]
            started = time.perf_counter()
            try:
                route, cost = intervention.build_route(compiled[code_hash], distances)
                runtime = time.perf_counter() - started
                routes[code_hash] = route
                runtimes[code_hash] = runtime
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "code_hash": code_hash,
                    "archive_role": candidate["archive_role"],
                    "tour_cost": cost,
                    "runtime_seconds": runtime,
                    "route_hash": intervention.route_hash(route),
                    "feasible": True,
                    "error_type": "",
                }
            except Exception as exc:  # 高规模失败必须留痕，不能删除慢或失败代码后重算。
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "code_hash": code_hash,
                    "archive_role": candidate["archive_role"],
                    "tour_cost": "",
                    "runtime_seconds": time.perf_counter() - started,
                    "route_hash": "",
                    "feasible": False,
                    "error_type": type(exc).__name__,
                }
            if (instance, code_hash) not in code_keys:
                append_row(code_path, CODE_FIELDS, row)
                code_keys.add((instance, code_hash))
        if not set(baseline_hashes) <= set(routes):
            raise RuntimeError(f"高规模实例的当前四槽不完整：{instance}")
        if instance not in comparison_instances:
            comparison = build_comparison(
                instance,
                distances,
                routes,
                runtimes,
                baseline_hashes,
                [item for item in portfolio_hashes if item in routes],
                protocol["repair"],
            )
            append_row(comparison_path, COMPARISON_FIELDS, comparison)
            comparison_instances.add(instance)
        del distances, routes
        gc.collect()

    code_rows, code_keys = load_existing(code_path, "coordinate")
    comparison_rows, comparison_instances = load_existing(comparison_path, "instance")
    expected = int(protocol["evaluation"]["expected_code_coordinate_count"])
    if len(code_keys) != expected or len(comparison_instances) != int(
        protocol["evaluation"]["instance_count"]
    ):
        raise RuntimeError("高规模输出坐标不完整")
    summary = summarize(protocol, code_rows, comparison_rows)
    summary.update(
        {
            "protocol_sha256": intervention.sha256_file(args.protocol),
            "frozen_portfolio_sha256": intervention.sha256_file(args.frozen_portfolio),
            "code_results_sha256": intervention.sha256_file(code_path),
            "comparison_sha256": intervention.sha256_file(comparison_path),
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
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--stage-bq-confirmation-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
