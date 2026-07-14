#!/usr/bin/env python3
"""在冻结的外部 TSPLIB 56 上评估全部目标规模安全代码。"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior
import audit_tsp_safe_pool_functional_redundancy as redundancy
import intervene_tsp_edge_variability as intervention


FIELDS = (
    "split",
    "instance",
    "nodes",
    "instance_sha256",
    "code_hash",
    "objective",
    "original_index",
    "cluster_id",
    "tour_cost",
    "runtime_seconds",
    "route_hash",
    "feasible",
    "error_type",
)


def load_protocol(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "instance_manifest_sha256": intervention.sha256_file(args.instance_manifest),
        "split_manifest_sha256": intervention.sha256_file(args.split_manifest),
        "safe_probe_results_sha256": intervention.sha256_file(args.safe_probe_results),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
        "stage_bp_clusters_sha256": intervention.sha256_file(args.stage_bp_clusters),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return protocol


def load_split(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    split_by_instance = {}
    for split_name in ("discovery", "confirmation"):
        for item in payload[split_name]:
            if item["instance"] in split_by_instance:
                raise ValueError(f"实例重复进入划分：{item['instance']}")
            split_by_instance[item["instance"]] = split_name
    return split_by_instance


def load_clusters(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["code_hash"]: int(row["cluster_id"]) for row in csv.DictReader(handle)}


def load_existing(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    keys = {(row["instance"], row["code_hash"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError(f"检查点包含重复坐标：{path}")
    return keys


def append_row(path: Path, row: dict[str, Any]) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        # 每个坐标立即落盘，长任务中断后只补缺口，不重复评估。
        handle.flush()


def count_rows(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows), sum(row["feasible"] == "True" for row in rows)


def run(args: argparse.Namespace) -> None:
    protocol = load_protocol(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "evaluation_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"评估已完成，禁止覆盖：{summary_path}")

    split_by_instance = load_split(args.split_manifest)
    expected_code_count = int(protocol["candidate_selection"]["expected_code_count"])
    candidates = redundancy.load_safe_candidates(
        args.safe_probe_results, args.code_catalog, expected_code_count
    )
    clusters = load_clusters(args.stage_bp_clusters)
    if set(clusters) != {item["code_hash"] for item in candidates}:
        raise ValueError("Stage BP 簇与 99 条安全代码不一致")

    compiled = {}
    compile_errors = {}
    for candidate in candidates:
        try:
            compiled[candidate["code_hash"]] = intervention.compile_heuristic(candidate["code"])
        except Exception as exc:  # 正式结果保留历史代码失败，不临时替换。
            compile_errors[candidate["code_hash"]] = exc

    output_paths = {
        "discovery": output_dir / "discovery_code_results.csv",
        "confirmation": output_dir / "confirmation_code_results.csv",
    }
    completed = {name: load_existing(path) for name, path in output_paths.items()}
    instances = intervention.load_instances(args.instance_manifest)
    if set(split_by_instance) != {item["name"] for item in instances}:
        raise ValueError("外部实例清单与冻结划分不一致")

    for instance_item in instances:
        instance = instance_item["name"]
        split_name = split_by_instance[instance]
        pending = [
            item
            for item in candidates
            if (instance, item["code_hash"]) not in completed[split_name]
        ]
        if not pending:
            continue
        coords = np.asarray(
            behavior.load_tsp(Path(instance_item["path"]))["coords"], dtype=float
        )
        distances = intervention.build_distance_matrix(coords)
        for candidate in pending:
            code_hash = candidate["code_hash"]
            started = time.perf_counter()
            try:
                compile_error = compile_errors.get(code_hash)
                if compile_error is not None:
                    raise compile_error
                route, cost = intervention.build_route(compiled[code_hash], distances)
                row = {
                    "split": split_name,
                    "instance": instance,
                    "nodes": len(coords),
                    "instance_sha256": instance_item["sha256"],
                    "code_hash": code_hash,
                    "objective": candidate["objective"],
                    "original_index": candidate["original_index"],
                    "cluster_id": clusters[code_hash],
                    "tour_cost": cost,
                    "runtime_seconds": time.perf_counter() - started,
                    "route_hash": intervention.route_hash(route),
                    "feasible": True,
                    "error_type": "",
                }
            except Exception as exc:  # 失败坐标继续写入，防止无声缩小候选池。
                row = {
                    "split": split_name,
                    "instance": instance,
                    "nodes": len(coords),
                    "instance_sha256": instance_item["sha256"],
                    "code_hash": code_hash,
                    "objective": candidate["objective"],
                    "original_index": candidate["original_index"],
                    "cluster_id": clusters[code_hash],
                    "tour_cost": "",
                    "runtime_seconds": time.perf_counter() - started,
                    "route_hash": "",
                    "feasible": False,
                    "error_type": type(exc).__name__,
                }
            append_row(output_paths[split_name], row)
            completed[split_name].add((instance, code_hash))
        del distances
        gc.collect()

    counts = {name: count_rows(path) for name, path in output_paths.items()}
    total_rows = sum(value[0] for value in counts.values())
    total_valid = sum(value[1] for value in counts.values())
    expected = int(protocol["evaluation"]["expected_coordinate_count"])
    summary = {
        "schema_version": "tsp-safe-pool-external56-evaluation/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "metrics": {
            "candidate_count": len(candidates),
            "instance_count": len(instances),
            "coordinate_count": total_rows,
            "valid_coordinate_count": total_valid,
            "discovery_coordinate_count": counts["discovery"][0],
            "confirmation_coordinate_count": counts["confirmation"][0],
        },
        "checks": {
            "coordinate_count_complete": total_rows == expected,
            "all_coordinates_valid": total_valid == expected,
            "split_balanced": counts["discovery"][0] == counts["confirmation"][0],
        },
        "discovery_results_sha256": intervention.sha256_file(output_paths["discovery"]),
        "confirmation_results_sha256": intervention.sha256_file(output_paths["confirmation"]),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--safe-probe-results", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--stage-bp-clusters", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
