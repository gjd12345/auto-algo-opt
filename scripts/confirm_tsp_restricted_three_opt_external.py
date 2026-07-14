#!/usr/bin/env python3
"""在 28 个冻结外部实例上确认受限三边重连的新增收益。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_iterated_nearest_two_opt as iterated
import evaluate_tsp_nearest_two_opt as nearest
import evaluate_tsp_or_opt_2_vnd as segment_move
import evaluate_tsp_relocation_vnd as relocation
import evaluate_tsp_restricted_three_opt as three_opt
import intervene_tsp_edge_variability as intervention


FIELDS = (
    "instance",
    "nodes",
    "winner_code_hash",
    "raw_baseline_cost",
    "stage_ca_cost",
    "restricted_three_opt_cost",
    "extra_vs_stage_ca_improvement_pct",
    "final_vs_raw_baseline_improvement_pct",
    "accepted_three_opt_count",
    "accepted_pattern_counts",
    "runtime_seconds",
    "feasible",
    "error_type",
)


def two_sided_sign_test_p_value(positive_count: int, nonzero_count: int) -> float:
    """计算零假设为胜负等概率时的双侧精确符号检验。"""
    if nonzero_count == 0:
        return 1.0
    smaller_tail = min(positive_count, nonzero_count - positive_count)
    tail_probability = sum(
        math.comb(nonzero_count, value) for value in range(smaller_tail + 1)
    ) / (2**nonzero_count)
    return min(1.0, 2.0 * tail_probability)


def load_protocol(args: argparse.Namespace) -> tuple[dict[str, Any], ...]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "split_manifest_sha256": intervention.sha256_file(args.split_manifest),
        "stage_bs_comparison_sha256": intervention.sha256_file(args.stage_bs_comparison),
        "stage_bt_protocol_sha256": intervention.sha256_file(args.stage_bt_protocol),
        "stage_bv_protocol_sha256": intervention.sha256_file(args.stage_bv_protocol),
        "stage_bw_protocol_sha256": intervention.sha256_file(args.stage_bw_protocol),
        "stage_bz_protocol_sha256": intervention.sha256_file(args.stage_bz_protocol),
        "stage_ca_protocol_sha256": intervention.sha256_file(args.stage_ca_protocol),
        "stage_ca_results_sha256": intervention.sha256_file(args.stage_ca_results),
        "stage_cb_protocol_sha256": intervention.sha256_file(args.stage_cb_protocol),
        "stage_cc_protocol_sha256": intervention.sha256_file(args.stage_cc_protocol),
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
        json.loads(args.stage_cc_protocol.read_text(encoding="utf-8")),
    )


def load_external_instances(
    protocol: dict[str, Any],
    instance_manifest: Path,
    split_manifest: Path,
) -> dict[str, dict[str, Any]]:
    split = json.loads(split_manifest.read_text(encoding="utf-8"))
    all_instances = {
        item["name"]: item for item in intervention.load_instances(instance_manifest)
    }
    split_name = protocol["split"]["name"]
    expected = {item["instance"]: item for item in split[split_name]}
    if len(expected) != int(protocol["split"]["instance_count"]):
        raise RuntimeError("冻结外部实例数不一致")
    instances = {name: all_instances[name] for name in expected}
    for name, item in instances.items():
        if item["sha256"] != expected[name]["sha256"]:
            raise RuntimeError(f"外部实例 hash 不匹配：{name}")
    return instances


def append_row(path: Path, row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def summarize(rows: list[dict[str, str]], protocol: dict[str, Any]) -> dict[str, Any]:
    extras = [float(row["extra_vs_stage_ca_improvement_pct"]) for row in rows]
    finals = [float(row["final_vs_raw_baseline_improvement_pct"]) for row in rows]
    valid_count = sum(row["feasible"] == "True" for row in rows)
    positive_count = sum(value > 0 for value in extras)
    pattern_counts: Counter[str] = Counter()
    for row in rows:
        pattern_counts.update(json.loads(row["accepted_pattern_counts"]))
    metrics = {
        "instance_count": len(rows),
        "valid_result_count": valid_count,
        "nonworse_than_stage_ca_instances": sum(value >= 0 for value in extras),
        "strictly_better_than_stage_ca_instances": positive_count,
        "mean_extra_improvement_pct": statistics.fmean(extras),
        "median_extra_improvement_pct": statistics.median(extras),
        "max_extra_improvement_pct": max(extras),
        "direction_sign_test_two_sided_p_value": two_sided_sign_test_p_value(
            positive_count, positive_count
        ),
        "final_mean_improvement_pct": statistics.fmean(finals),
        "final_median_improvement_pct": statistics.median(finals),
        "final_max_improvement_pct": max(finals),
        "accepted_three_opt_count": sum(
            int(row["accepted_three_opt_count"]) for row in rows
        ),
        "accepted_pattern_counts": dict(sorted(pattern_counts.items())),
        "median_runtime_seconds": statistics.median(
            float(row["runtime_seconds"]) for row in rows
        ),
    }
    gate = protocol["primary_gate"]
    checks = {
        "valid_results": valid_count >= gate["valid_result_count_min"],
        "nonworse": metrics["nonworse_than_stage_ca_instances"]
        >= gate["nonworse_than_stage_ca_instances_min"],
        "strictly_better": metrics["strictly_better_than_stage_ca_instances"]
        >= gate["strictly_better_than_stage_ca_instances_min"],
        "median_extra": metrics["median_extra_improvement_pct"]
        >= gate["median_extra_improvement_pct_min"],
    }
    return {
        "schema_version": "tsp-restricted-three-opt-external-summary/v1",
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
        stage_cc_protocol,
    ) = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "external_restricted_three_opt_results.csv"
    summary_path = output_dir / "external_restricted_three_opt_summary.json"
    if summary_path.exists():
        raise FileExistsError("受限 3-opt 外部确认已完成，禁止覆盖")

    instances = load_external_instances(
        protocol, args.instance_manifest, args.split_manifest
    )
    comparison_rows = {
        row["instance"]: row for row in relocation.load_csv(args.stage_bs_comparison)
    }
    comparison_rows = {
        instance: comparison_rows[instance] for instance in instances
    }
    stage_ca_rows = {
        row["instance"]: row for row in relocation.load_csv(args.stage_ca_results)
    }
    if set(stage_ca_rows) != set(instances):
        raise RuntimeError("Stage CA 结果与冻结外部实例不一致")

    winner_hashes = {
        instance: row["portfolio_winner"]
        for instance, row in comparison_rows.items()
    }
    codes = relocation.load_codes(args.code_catalog, set(winner_hashes.values()))
    compiled = {
        code_hash: intervention.compile_heuristic(code)
        for code_hash, code in codes.items()
    }
    existing_rows = relocation.load_csv(result_path) if result_path.exists() else []
    completed = {row["instance"] for row in existing_rows}
    if len(completed) != len(existing_rows):
        raise RuntimeError("受限 3-opt 外部检查点存在重复实例")

    for instance, item in instances.items():
        if instance in completed:
            continue
        comparison = comparison_rows[instance]
        winner_hash = winner_hashes[instance]
        coords = np.asarray(behavior.load_tsp(Path(item["path"]))["coords"], dtype=float)
        distances = intervention.build_distance_matrix(coords)
        neighbors = nearest.build_nearest_neighbors(
            distances,
            int(stage_cc_protocol["search"]["nearest_neighbor_count"]),
            int(stage_cc_protocol["search"]["neighbor_build_block_size"]),
        )
        raw_baseline_cost = float(comparison["raw_baseline_cost"])
        try:
            raw_route, raw_portfolio_cost = intervention.build_route(
                compiled[winner_hash], distances
            )
            if raw_portfolio_cost != float(comparison["raw_portfolio_cost"]):
                raise RuntimeError("Stage BS 组合赢家重放成本不一致")
            stage_bt_route = iterated.run_search(
                raw_route,
                distances,
                neighbors,
                instance,
                "portfolio",
                stage_bt_protocol["search"],
            )["best_route"]
            stage_bv_route, _, _, _ = relocation.run_vnd(
                stage_bt_route, distances, neighbors, stage_bv_protocol["search"]
            )
            stage_bw_route, _, _, _, _ = segment_move.run_or_opt_2_vnd(
                stage_bv_route,
                distances,
                neighbors,
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            stage_ca_route = three_opt.run_or_opt_3_vnd(
                stage_bw_route,
                distances,
                neighbors,
                stage_bz_protocol["search"],
                stage_bw_protocol["search"],
                stage_bv_protocol["search"],
            )
            stage_ca_cost = intervention.route_cost(stage_ca_route, distances)
            if stage_ca_cost != float(stage_ca_rows[instance]["or_opt_3_cost"]):
                raise RuntimeError("Stage CA 重放成本不一致")
            final_route, patterns, runtime = three_opt.run_restricted_three_opt(
                stage_ca_route,
                distances,
                neighbors,
                stage_cc_protocol["search"],
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
                "stage_ca_cost": stage_ca_cost,
                "restricted_three_opt_cost": final_cost,
                "extra_vs_stage_ca_improvement_pct": relocation.improvement(
                    stage_ca_cost, final_cost
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
        except Exception as exc:  # 外部失败坐标必须保留，禁止事后换实例。
            row = {
                "instance": instance,
                "nodes": len(coords),
                "winner_code_hash": winner_hash,
                "raw_baseline_cost": raw_baseline_cost,
                "stage_ca_cost": stage_ca_rows[instance]["or_opt_3_cost"],
                "restricted_three_opt_cost": "",
                "extra_vs_stage_ca_improvement_pct": "",
                "final_vs_raw_baseline_improvement_pct": "",
                "accepted_three_opt_count": "",
                "accepted_pattern_counts": "",
                "runtime_seconds": "",
                "feasible": False,
                "error_type": type(exc).__name__,
            }
        append_row(result_path, row)
        completed.add(instance)

    rows = relocation.load_csv(result_path)
    if len(rows) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("受限 3-opt 外部结果不完整")
    if any(row["feasible"] != "True" for row in rows):
        raise RuntimeError("受限 3-opt 外部存在失败坐标，禁止生成成功摘要")
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
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--stage-bs-comparison", type=Path, required=True)
    parser.add_argument("--stage-bt-protocol", type=Path, required=True)
    parser.add_argument("--stage-bv-protocol", type=Path, required=True)
    parser.add_argument("--stage-bw-protocol", type=Path, required=True)
    parser.add_argument("--stage-bz-protocol", type=Path, required=True)
    parser.add_argument("--stage-ca-protocol", type=Path, required=True)
    parser.add_argument("--stage-ca-results", type=Path, required=True)
    parser.add_argument("--stage-cb-protocol", type=Path, required=True)
    parser.add_argument("--stage-cc-protocol", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
