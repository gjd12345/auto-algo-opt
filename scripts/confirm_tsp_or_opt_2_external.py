#!/usr/bin/env python3
"""在冻结的外部确认实例上检验 Or-opt-2 的新增收益。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import evaluate_tsp_iterated_nearest_two_opt as iterated
import evaluate_tsp_nearest_two_opt as nearest
import evaluate_tsp_or_opt_2_vnd as or_opt_2
import evaluate_tsp_relocation_vnd as relocation
import intervene_tsp_edge_variability as intervention


def load_protocol(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "split_manifest_sha256": intervention.sha256_file(args.split_manifest),
        "stage_bs_confirmation_sha256": intervention.sha256_file(
            args.stage_bs_confirmation
        ),
        "stage_bt_protocol_sha256": intervention.sha256_file(args.stage_bt_protocol),
        "stage_bv_protocol_sha256": intervention.sha256_file(args.stage_bv_protocol),
        "stage_bw_protocol_sha256": intervention.sha256_file(args.stage_bw_protocol),
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
    )


def run(args: argparse.Namespace) -> None:
    protocol, stage_bt_protocol, stage_bv_protocol, stage_bw_protocol = load_protocol(
        args
    )
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "external_or_opt_2_results.csv"
    summary_path = output_dir / "external_or_opt_2_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"外部 Or-opt-2 确认已完成：{summary_path}")

    split = json.loads(args.split_manifest.read_text(encoding="utf-8"))
    expected_instances = {item["instance"]: item for item in split["confirmation"]}
    if len(expected_instances) != int(protocol["split"]["instance_count"]):
        raise RuntimeError("冻结 confirmation 实例数不一致")
    all_instances = {
        item["name"]: item for item in intervention.load_instances(args.instance_manifest)
    }
    instances = {name: all_instances[name] for name in expected_instances}
    for name, item in instances.items():
        if item["sha256"] != expected_instances[name]["sha256"]:
            raise RuntimeError(f"外部实例 hash 不匹配：{name}")

    comparison_rows = {
        row["instance"]: row for row in relocation.load_csv(args.stage_bs_confirmation)
    }
    if set(comparison_rows) != set(instances):
        raise RuntimeError("Stage BS 确认实例与冻结划分不一致")
    winner_by_key: dict[tuple[str, str], str] = {}
    raw_cost_by_key: dict[tuple[str, str], float] = {}
    for instance, row in comparison_rows.items():
        winner_by_key[(instance, "baseline")] = row["baseline_winner"]
        winner_by_key[(instance, "portfolio")] = row["portfolio_winner"]
        raw_cost_by_key[(instance, "baseline")] = float(row["raw_baseline_cost"])
        raw_cost_by_key[(instance, "portfolio")] = float(row["raw_portfolio_cost"])

    required_hashes = set(winner_by_key.values())
    codes = relocation.load_codes(args.code_catalog, required_hashes)
    compiled = {
        code_hash: intervention.compile_heuristic(code) for code_hash, code in codes.items()
    }
    _, completed = or_opt_2.load_existing(result_path)
    stage_bt_search = stage_bt_protocol["search"]
    stage_bv_search = stage_bv_protocol["search"]
    stage_bw_search = stage_bw_protocol["search"]
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
            int(stage_bw_search["nearest_neighbor_count"]),
            int(stage_bw_search["neighbor_build_block_size"]),
        )
        for role in pending_roles:
            key = (instance, role)
            winner_hash = winner_by_key[key]
            try:
                route, raw_cost = intervention.build_route(compiled[winner_hash], distances)
                if raw_cost != raw_cost_by_key[key]:
                    raise RuntimeError("原路线成本与 Stage BS 不一致")
                stage_bt_route = iterated.run_search(
                    route, distances, neighbors, instance, role, stage_bt_search
                )["best_route"]
                stage_bv_route, _, _, _ = relocation.run_vnd(
                    stage_bt_route, distances, neighbors, stage_bv_search
                )
                stage_bv_cost = intervention.route_cost(stage_bv_route, distances)
                final_route, moves, relocations, two_opt_steps, runtime = (
                    or_opt_2.run_or_opt_2_vnd(
                        stage_bv_route,
                        distances,
                        neighbors,
                        stage_bw_search,
                        stage_bv_search,
                    )
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
            except Exception as exc:  # 外部确认失败必须保留坐标，不事后换实例。
                row = {
                    "instance": instance,
                    "nodes": len(coords),
                    "archive_role": role,
                    "winner_code_hash": winner_hash,
                    "raw_cost": raw_cost_by_key[key],
                    "stage_bv_cost": "",
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
            or_opt_2.append_row(result_path, row)
            completed.add(key)

    rows, completed = or_opt_2.load_existing(result_path)
    if len(completed) != int(protocol["evaluation"]["expected_result_count"]):
        raise RuntimeError("外部 Or-opt-2 结果不完整")
    if any(row["feasible"] != "True" for row in rows):
        raise RuntimeError("外部确认存在失败坐标，禁止生成成功摘要")
    summary = or_opt_2.summarize(rows, protocol)
    summary.update(
        {
            "schema_version": "tsp-or-opt-2-external-confirmation-summary/v1",
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
    parser.add_argument("--stage-bs-confirmation", type=Path, required=True)
    parser.add_argument("--stage-bt-protocol", type=Path, required=True)
    parser.add_argument("--stage-bv-protocol", type=Path, required=True)
    parser.add_argument("--stage-bw-protocol", type=Path, required=True)
    parser.add_argument("--frozen-portfolio", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
