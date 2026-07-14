#!/usr/bin/env python3
"""在冻结发现集选 TSP 高收益组合，再对未见确认集做一次性检验。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

import intervene_tsp_edge_variability as intervention


def load_protocol(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if intervention.sha256_file(args.split_manifest) != protocol["inputs"]["split_manifest_sha256"]:
        raise RuntimeError("冻结划分 hash 不匹配")
    return protocol


def load_split(path: Path, split_name: str) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item["instance"] for item in payload[split_name]]


def load_results(
    path: Path,
    expected_sha256: str,
    expected_instances: list[str],
    expected_code_count: int,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    if intervention.sha256_file(path) != expected_sha256:
        raise RuntimeError(f"结果 hash 不匹配：{path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_coordinate = {(row["instance"], row["code_hash"]): row for row in rows}
    expected_count = len(expected_instances) * expected_code_count
    if len(rows) != expected_count or len(by_coordinate) != expected_count:
        raise ValueError("结果坐标数量不完整或重复")
    if {row["instance"] for row in rows} != set(expected_instances):
        raise ValueError("结果包含当前阶段之外的实例")
    if any(row["feasible"] != "True" for row in rows):
        raise ValueError("存在不可行坐标，禁止静默缩小候选池")
    return rows, by_coordinate


def candidate_metadata(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata = {}
    for row in rows:
        code_hash = row["code_hash"]
        item = {
            "code_hash": code_hash,
            "objective": float(row["objective"]),
            "original_index": int(row["original_index"]),
            "cluster_id": int(row["cluster_id"]),
        }
        if code_hash in metadata and metadata[code_hash] != item:
            raise ValueError(f"代码元数据不一致：{code_hash}")
        metadata[code_hash] = item
    return metadata


def best_costs(
    instances: list[str],
    codes: list[str],
    by_coordinate: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, float], dict[str, str]]:
    costs = {}
    winners = {}
    for instance in instances:
        winner = min(
            codes,
            key=lambda code_hash: (
                float(by_coordinate[(instance, code_hash)]["tour_cost"]),
                code_hash,
            ),
        )
        costs[instance] = float(by_coordinate[(instance, winner)]["tour_cost"])
        winners[instance] = winner
    return costs, winners


def improvements(base: dict[str, float], trial: dict[str, float]) -> list[float]:
    return [(base[name] - trial[name]) / base[name] * 100.0 for name in base]


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有结果：{path}")
    columns = fieldnames or (list(rows[0]) if rows else [])
    if not columns:
        raise ValueError(f"空结果缺少列定义：{path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_discovery(args: argparse.Namespace, protocol: dict[str, Any]) -> None:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = output_dir / "frozen_quality_portfolio.json"
    if frozen_path.exists():
        raise FileExistsError(f"发现组合已冻结：{frozen_path}")

    instances = load_split(args.split_manifest, "discovery")
    expected_code_count = int(protocol["candidate_selection"]["expected_code_count"])
    rows, by_coordinate = load_results(
        args.discovery_results,
        args.expected_discovery_sha256,
        instances,
        expected_code_count,
    )
    metadata = candidate_metadata(rows)
    baseline = list(protocol["candidate_selection"]["baseline_code_hashes"])
    if not set(baseline) <= set(metadata):
        raise ValueError("当前四槽不在安全候选集中")
    baseline_costs, _ = best_costs(instances, baseline, by_coordinate)

    candidates = sorted(set(metadata) - set(baseline))
    selected: list[str] = []
    current_codes = list(baseline)
    current_mean = 0.0
    steps = []
    max_added = int(protocol["discovery_selection"]["maximum_added_codes"])
    for step in range(1, max_added + 1):
        scored = []
        for code_hash in candidates:
            trial_costs, _ = best_costs(
                instances, current_codes + [code_hash], by_coordinate
            )
            values = improvements(baseline_costs, trial_costs)
            mean_value = statistics.fmean(values)
            median_value = statistics.median(values)
            item = metadata[code_hash]
            scored.append(
                (
                    -mean_value,
                    -median_value,
                    -item["objective"],
                    item["original_index"],
                    code_hash,
                    trial_costs,
                    values,
                )
            )
        if not scored:
            break
        best = min(scored)
        mean_value = -best[0]
        if mean_value <= current_mean + 1e-12:
            break
        code_hash = best[4]
        values = best[6]
        selected.append(code_hash)
        current_codes.append(code_hash)
        candidates.remove(code_hash)
        marginal = mean_value - current_mean
        current_mean = mean_value
        steps.append(
            {
                "step": step,
                "added_code_hash": code_hash,
                "cluster_id": metadata[code_hash]["cluster_id"],
                "objective": metadata[code_hash]["objective"],
                "original_index": metadata[code_hash]["original_index"],
                "mean_improvement_pct": mean_value,
                "median_improvement_pct": statistics.median(values),
                "max_improvement_pct": max(values),
                "improved_instance_count": sum(value > 0 for value in values),
                "marginal_mean_improvement_pct": marginal,
            }
        )

    write_csv(
        output_dir / "discovery_portfolio_curve.csv",
        steps,
        fieldnames=[
            "step",
            "added_code_hash",
            "cluster_id",
            "objective",
            "original_index",
            "mean_improvement_pct",
            "median_improvement_pct",
            "max_improvement_pct",
            "improved_instance_count",
            "marginal_mean_improvement_pct",
        ],
    )
    frozen = {
        "schema_version": "tsp-quality-first-frozen-portfolio/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "discovery_results_sha256": intervention.sha256_file(args.discovery_results),
        # 这里只记录调用方提供的确认文件 hash；发现阶段从不打开确认结果。
        "confirmation_results_sha256": args.expected_confirmation_sha256,
        "baseline_code_hashes": baseline,
        "selected_addition_code_hashes": selected,
        "portfolio_code_hashes": baseline + selected,
        "selected_cluster_ids": [metadata[item]["cluster_id"] for item in selected],
        "discovery_instance_count": len(instances),
        "discovery_coordinate_count": len(rows),
        "selection_steps": steps,
        "confirmation_results_read": False,
        "next_action": "confirm_once_with_expected_portfolio_sha256",
    }
    frozen_path.write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"FROZEN_PORTFOLIO_SHA256={intervention.sha256_file(frozen_path)}\n"
        f"SELECTED_ADDITIONS={','.join(selected)}"
    )


def two_sided_sign_test(wins: int, losses: int) -> float:
    sample_count = wins + losses
    if sample_count == 0:
        return 1.0
    tail = sum(math.comb(sample_count, value) for value in range(0, min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**sample_count))


def run_confirmation(args: argparse.Namespace, protocol: dict[str, Any]) -> None:
    frozen_path = args.frozen_portfolio.resolve()
    if intervention.sha256_file(frozen_path) != args.expected_portfolio_sha256:
        raise RuntimeError("冻结组合 hash 不匹配")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if intervention.sha256_file(args.confirmation_results) != frozen["confirmation_results_sha256"]:
        raise RuntimeError("确认结果 hash 与冻结组合不匹配")

    output_dir = args.output_dir.resolve()
    summary_path = output_dir / "confirmation_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"确认结果已存在：{summary_path}")
    instances = load_split(args.split_manifest, "confirmation")
    expected_code_count = int(protocol["candidate_selection"]["expected_code_count"])
    rows, by_coordinate = load_results(
        args.confirmation_results,
        frozen["confirmation_results_sha256"],
        instances,
        expected_code_count,
    )
    baseline = frozen["baseline_code_hashes"]
    additions = frozen["selected_addition_code_hashes"]
    baseline_costs, baseline_winners = best_costs(instances, baseline, by_coordinate)
    full_costs, full_winners = best_costs(
        instances,
        sorted({row["code_hash"] for row in rows}),
        by_coordinate,
    )
    full_values = improvements(baseline_costs, full_costs)

    curve_rows = []
    final_costs = baseline_costs
    final_winners = baseline_winners
    for count in range(0, len(additions) + 1):
        codes = baseline + additions[:count]
        costs, winners = best_costs(instances, codes, by_coordinate)
        values = improvements(baseline_costs, costs)
        regrets = [(costs[name] / full_costs[name] - 1.0) * 100.0 for name in instances]
        runtime_ratios = []
        for instance in instances:
            base_runtime = sum(
                float(by_coordinate[(instance, code_hash)]["runtime_seconds"])
                for code_hash in baseline
            )
            portfolio_runtime = sum(
                float(by_coordinate[(instance, code_hash)]["runtime_seconds"])
                for code_hash in codes
            )
            runtime_ratios.append(portfolio_runtime / base_runtime)
        curve_rows.append(
            {
                "added_code_count": count,
                "total_code_count": len(codes),
                "mean_improvement_pct": statistics.fmean(values),
                "median_improvement_pct": statistics.median(values),
                "max_improvement_pct": max(values),
                "win_count": sum(value > 0 for value in values),
                "same_count": sum(value == 0 for value in values),
                "loss_count": sum(value < 0 for value in values),
                "exact_full_oracle_matches": sum(regret == 0 for regret in regrets),
                "mean_regret_to_full_oracle_pct": statistics.fmean(regrets),
                "max_regret_to_full_oracle_pct": max(regrets),
                "median_runtime_ratio_vs_baseline": statistics.median(runtime_ratios),
            }
        )
        if count == len(additions):
            final_costs, final_winners = costs, winners

    instance_rows = []
    for instance in instances:
        value = (baseline_costs[instance] - final_costs[instance]) / baseline_costs[instance] * 100
        instance_rows.append(
            {
                "instance": instance,
                "baseline_winner": baseline_winners[instance],
                "portfolio_winner": final_winners[instance],
                "full_oracle_winner": full_winners[instance],
                "baseline_cost": baseline_costs[instance],
                "portfolio_cost": final_costs[instance],
                "full_oracle_cost": full_costs[instance],
                "improvement_pct": value,
                "portfolio_regret_to_full_pct":
                    (final_costs[instance] / full_costs[instance] - 1.0) * 100,
            }
        )
    write_csv(output_dir / "confirmation_portfolio_curve.csv", curve_rows)
    write_csv(output_dir / "confirmation_instance_comparison.csv", instance_rows)

    primary = curve_rows[-1]
    gates = protocol["confirmation_gate"]
    total_coordinate_count = len(rows) + int(frozen["discovery_coordinate_count"])
    checks = {
        "feasible_coordinates": total_coordinate_count == gates["feasible_coordinate_count"],
        "no_losses": primary["loss_count"] <= gates["portfolio_losses_vs_baseline_max"],
        "wins": primary["win_count"] >= gates["portfolio_wins_vs_baseline_min"],
        "median_improvement": primary["median_improvement_pct"]
        >= gates["median_cost_improvement_pct_min"],
        "mean_improvement": primary["mean_improvement_pct"]
        >= gates["mean_cost_improvement_pct_min"],
    }
    summary = {
        "schema_version": "tsp-quality-first-portfolio-confirmation/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "frozen_portfolio_sha256": intervention.sha256_file(frozen_path),
        "selected_addition_count": len(additions),
        "selected_addition_code_hashes": additions,
        "selected_cluster_ids": frozen["selected_cluster_ids"],
        "metrics": {
            **primary,
            "two_sided_sign_test_p": two_sided_sign_test(
                int(primary["win_count"]), int(primary["loss_count"])
            ),
            "full_99_mean_improvement_upper_bound_pct": statistics.fmean(full_values),
            "full_99_median_improvement_upper_bound_pct": statistics.median(full_values),
            "captured_mean_upper_bound_fraction": (
                float(primary["mean_improvement_pct"]) / statistics.fmean(full_values)
                if statistics.fmean(full_values) > 0
                else 1.0
            ),
        },
        "checks": checks,
        "decision": (
            protocol["decision"]["all_checks_pass"]
            if all(checks.values())
            else protocol["decision"]["otherwise"]
        ),
        "default_pool_behavior": "unchanged",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("discover", "confirm"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--discovery-results", type=Path)
    parser.add_argument("--confirmation-results", type=Path)
    parser.add_argument("--expected-discovery-sha256")
    parser.add_argument("--expected-confirmation-sha256")
    parser.add_argument("--frozen-portfolio", type=Path)
    parser.add_argument("--expected-portfolio-sha256")
    args = parser.parse_args()
    if args.phase == "discover" and (
        args.discovery_results is None
        or not args.expected_discovery_sha256
        or not args.expected_confirmation_sha256
    ):
        parser.error("discover 必须提供发现结果及发现/确认结果的冻结 hash")
    if args.phase == "confirm" and (
        args.confirmation_results is None
        or args.frozen_portfolio is None
        or not args.expected_portfolio_sha256
    ):
        parser.error("confirm 必须提供确认结果、冻结组合及其预期 hash")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    frozen_protocol = load_protocol(parsed)
    if parsed.phase == "discover":
        run_discovery(parsed, frozen_protocol)
    else:
        run_confirmation(parsed, frozen_protocol)
