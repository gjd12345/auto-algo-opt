#!/usr/bin/env python3
"""在已判规模安全的 TSP 代码内构建质量与速度前沿。"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_tsp_history_scalability as audit
import audit_tsp_runtime_probe_frontier as base


MANIFEST_NAME = "safe_pool_frontier_manifest.json"
RESULT_FIELDS = (
    "code_hash",
    "objective",
    "original_index",
    "ast_nodes",
    "instance",
    "instance_seed",
    "instance_sha256",
    "timeout_s",
    "wall_time_s",
    "feasible",
    "tour_cost",
    "error_type",
    "error",
    "source",
)
MIN_FULLY_FEASIBLE = 90
SELECTED_COUNT = 4
MIN_COST_SIGNATURES = 2
MIN_MEDIAN_IMPROVEMENT_PCT = 0.1


def load_aw_safe_hashes(stage_aw_dir: Path) -> list[str]:
    prediction_path = stage_aw_dir / "direct_scale_predictions_frozen.csv"
    lock_path = stage_aw_dir / "direct_scale_prediction_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock["prediction_sha256"] != audit.sha256_file(prediction_path):
        raise RuntimeError("Stage AW 冻结预测 hash 不匹配")
    if lock.get("labels_loaded") is not False:
        raise RuntimeError("Stage AW 预测锁缺少 labels_loaded=false 声明")
    rows = base.read_csv(prediction_path)
    hashes = [row["code_hash"] for row in rows if base.bool_value(row["predicted_scale_safe"])]
    if len(hashes) != 99 or len(hashes) != len(set(hashes)):
        raise RuntimeError(f"Stage AW 安全集合应为 99 条，实际为 {len(hashes)}")
    return hashes


def prepare(output_dir: Path, catalog_path: Path, stage_aw_dir: Path, stage_ax_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"前沿清单已存在，禁止覆盖：{manifest_path}")

    catalog_path = catalog_path.resolve()
    stage_aw_dir = stage_aw_dir.resolve()
    stage_ax_dir = stage_ax_dir.resolve()
    catalog = base.read_jsonl(catalog_path)
    base.validate_catalog(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    safe_hashes = load_aw_safe_hashes(stage_aw_dir)
    if not set(safe_hashes) <= set(catalog_by_hash):
        raise RuntimeError("Stage AW 安全集合包含历史目录外代码")

    stage_ax_manifest_path = stage_ax_dir / "scale_archive_confirmation_manifest.json"
    stage_ax_results_path = stage_ax_dir / "scale_archive_confirmation_results.csv"
    stage_ax_summary_path = stage_ax_dir / "scale_archive_confirmation_summary.json"
    stage_ax_manifest = json.loads(stage_ax_manifest_path.read_text(encoding="utf-8"))
    stage_ax_summary = json.loads(stage_ax_summary_path.read_text(encoding="utf-8"))
    if not stage_ax_summary.get("overall_pass"):
        raise RuntimeError("Stage AX 未通过，不能将其实例转作前沿发现集")

    instances = stage_ax_manifest["instances"]
    candidates = [
        {
            "code_hash": row["code_hash"],
            "objective": row["objective"],
            "original_index": row["original_index"],
            "ast_nodes": row["ast_nodes"],
        }
        for row in catalog
        if row["code_hash"] in set(safe_hashes)
    ]
    manifest = {
        "schema_version": "tsp-safe-pool-frontier/v1",
        "study_role": "discovery_with_previously_confirmed_instances",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "inputs": {
            "catalog": {"path": str(catalog_path), "sha256": audit.sha256_file(catalog_path)},
            "stage_aw_predictions": {
                "path": str(stage_aw_dir / "direct_scale_predictions_frozen.csv"),
                "sha256": audit.sha256_file(stage_aw_dir / "direct_scale_predictions_frozen.csv"),
            },
            "stage_ax_manifest": {
                "path": str(stage_ax_manifest_path),
                "sha256": audit.sha256_file(stage_ax_manifest_path),
            },
            "stage_ax_results": {
                "path": str(stage_ax_results_path),
                "sha256": audit.sha256_file(stage_ax_results_path),
            },
            "stage_ax_summary": {
                "path": str(stage_ax_summary_path),
                "sha256": audit.sha256_file(stage_ax_summary_path),
            },
        },
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "safe_code_hashes": safe_hashes,
        "candidates": candidates,
        "instances": instances,
        "timeout_s": float(stage_ax_manifest["timeout_s"]),
        "current_aw_archive": stage_ax_manifest["archives"]["aw_scale"],
        "expected_coordinates": len(candidates) * len(instances),
        "gate": {
            "fully_feasible_codes_min": MIN_FULLY_FEASIBLE,
            "selected_coordinates_feasible": SELECTED_COUNT * len(instances),
            "selected_cost_signatures_min": MIN_COST_SIGNATURES,
            "median_improvement_vs_current_aw_min_pct": MIN_MEDIAN_IMPROVEMENT_PCT,
        },
        "selection_rule": "三实例均可行后，按中位相对成本、运行时间、AST 节点数排序，并优先保留不同路线成本签名",
        "confirmation_rule": "发现门槛通过后必须在全新实例确认，当前三实例不得同时用于最终结论",
    }
    audit.write_json(manifest_path, manifest)
    reusable = {
        (row["code_hash"], row["instance"])
        for row in base.read_csv(stage_ax_results_path)
        if row["code_hash"] in set(safe_hashes)
    }
    print(
        json.dumps(
            {
                "prepared": True,
                "safe_codes": len(candidates),
                "coordinates": manifest["expected_coordinates"],
                "reusable_coordinates": len(reusable),
                "new_coordinates": manifest["expected_coordinates"] - len(reusable),
                "manifest_sha256": audit.sha256_file(manifest_path),
            },
            ensure_ascii=False,
        )
    )


def load_frozen_inputs(output_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    for name, frozen in manifest["inputs"].items():
        if audit.sha256_file(Path(frozen["path"])) != frozen["sha256"]:
            raise RuntimeError(f"冻结输入 hash 不匹配：{name}")
    if audit.sha256_file(audit.EVALUATOR_PATH) != manifest["evaluator_sha256"]:
        raise RuntimeError("评估器在前沿清单冻结后发生变化")
    for instance in manifest["instances"]:
        if audit.sha256_file(Path(instance["path"])) != instance["sha256"]:
            raise RuntimeError(f"发现实例 hash 不匹配：{instance['name']}")

    catalog = base.read_jsonl(Path(manifest["inputs"]["catalog"]["path"]))
    base.validate_catalog(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    if set(manifest["safe_code_hashes"]) != {row["code_hash"] for row in manifest["candidates"]}:
        raise RuntimeError("冻结安全代码集合不一致")
    return manifest, catalog_by_hash


def result_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["code_hash"]), str(row["instance"])


def seed_reusable_rows(output_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    results_path = output_dir / "safe_pool_frontier_results.csv"
    if results_path.exists():
        return base.read_csv(results_path)
    safe_hashes = set(manifest["safe_code_hashes"])
    source_rows = base.read_csv(Path(manifest["inputs"]["stage_ax_results"]["path"]))
    for source in source_rows:
        if source["code_hash"] not in safe_hashes:
            continue
        row = {field: source.get(field, "") for field in RESULT_FIELDS}
        row["source"] = "reused_stage_ax"
        base.append_csv(results_path, row, RESULT_FIELDS)
    return base.read_csv(results_path)


def run_coordinates(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog_by_hash: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results_path = output_dir / "safe_pool_frontier_results.csv"
    rows = seed_reusable_rows(output_dir, manifest)
    completed = {result_key(row) for row in rows}
    if len(completed) != len(rows):
        raise RuntimeError("前沿结果包含重复坐标")

    evaluator = audit.import_evaluator()
    total = int(manifest["expected_coordinates"])
    for frozen in manifest["candidates"]:
        candidate = catalog_by_hash[frozen["code_hash"]]
        for instance in manifest["instances"]:
            key = (candidate["code_hash"], instance["name"])
            if key in completed:
                continue
            started_at = time.perf_counter()
            try:
                result = evaluator(candidate["code"], instance["path"], float(manifest["timeout_s"]))
            except Exception as exc:  # 单条失败必须保留，不能中断 99 条安全集合的完整审计。
                result = {
                    "feasible": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            row = {
                **frozen,
                "instance": instance["name"],
                "instance_seed": instance["seed"],
                "instance_sha256": instance["sha256"],
                "timeout_s": manifest["timeout_s"],
                "wall_time_s": round(time.perf_counter() - started_at, 6),
                "feasible": bool(result.get("feasible", False)),
                "tour_cost": result.get("tour_cost"),
                "error_type": result.get("error_type", ""),
                "error": result.get("error", ""),
                "source": "new_stage_ay",
            }
            base.append_csv(results_path, row, RESULT_FIELDS)
            rows.append(row)
            completed.add(key)
            if len(rows) % 10 == 0 or len(rows) == total:
                print(json.dumps({"coordinates": len(rows), "total": total}), flush=True)
    if len(rows) != total:
        raise RuntimeError(f"冻结坐标未完成：{len(rows)}/{total}")
    return rows


def candidate_metrics(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    instance_names = [instance["name"] for instance in manifest["instances"]]
    feasible_costs_by_instance = {
        name: [
            float(row["tour_cost"])
            for row in rows
            if row["instance"] == name
            and audit.feasible_value(row["feasible"])
            and row.get("tour_cost") not in (None, "")
        ]
        for name in instance_names
    }
    best_by_instance = {name: min(costs) for name, costs in feasible_costs_by_instance.items() if costs}
    metrics = []
    for candidate in manifest["candidates"]:
        code_rows = [row for row in rows if row["code_hash"] == candidate["code_hash"]]
        feasible_rows = [row for row in code_rows if audit.feasible_value(row["feasible"])]
        full_feasible = len(feasible_rows) == len(instance_names)
        costs = {
            row["instance"]: float(row["tour_cost"])
            for row in feasible_rows
            if row.get("tour_cost") not in (None, "")
        }
        relative_costs = [
            (costs[name] - best_by_instance[name]) / best_by_instance[name] * 100.0
            for name in instance_names
            if name in costs and name in best_by_instance
        ]
        signature = "|".join(str(int(round(costs[name]))) for name in instance_names) if full_feasible else ""
        metrics.append(
            {
                **candidate,
                "feasible_coordinates": len(feasible_rows),
                "full_feasible": full_feasible,
                "median_relative_cost_pct": statistics.median(relative_costs) if full_feasible else None,
                "median_runtime_s": statistics.median(float(row["wall_time_s"]) for row in feasible_rows)
                if feasible_rows
                else None,
                "cost_signature": signature,
            }
        )
    return metrics


def select_archive(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [row for row in metrics if row["full_feasible"]]
    eligible.sort(
        key=lambda row: (
            float(row["median_relative_cost_pct"]),
            float(row["median_runtime_s"]),
            int(row["ast_nodes"]),
            int(row["original_index"]),
        )
    )
    selected = []
    used_signatures = set()
    for row in eligible:
        if row["cost_signature"] in used_signatures:
            continue
        selected.append(row)
        used_signatures.add(row["cost_signature"])
        if len(selected) == SELECTED_COUNT:
            return selected
    for row in eligible:
        if row in selected:
            continue
        selected.append(row)
        if len(selected) == SELECTED_COUNT:
            break
    return selected


def archive_best_costs(hashes: set[str], instances: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, float | None]:
    result = {}
    for instance in instances:
        costs = [
            float(row["tour_cost"])
            for row in rows
            if row["code_hash"] in hashes
            and row["instance"] == instance["name"]
            and audit.feasible_value(row["feasible"])
            and row.get("tour_cost") not in (None, "")
        ]
        result[instance["name"]] = min(costs) if costs else None
    return result


def summarize(output_dir: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    metrics = candidate_metrics(manifest, rows)
    base.write_csv(output_dir / "safe_pool_candidate_metrics.csv", metrics)
    selected = select_archive(metrics)
    selected_hashes = {row["code_hash"] for row in selected}
    current_hashes = set(manifest["current_aw_archive"])
    selected_best = archive_best_costs(selected_hashes, manifest["instances"], rows)
    current_best = archive_best_costs(current_hashes, manifest["instances"], rows)

    comparisons = []
    for instance in manifest["instances"]:
        name = instance["name"]
        selected_cost = selected_best[name]
        current_cost = current_best[name]
        diff_pct = None
        if selected_cost is not None and current_cost is not None:
            diff_pct = (selected_cost - current_cost) / current_cost * 100.0
        comparisons.append(
            {
                "instance": name,
                "selected_best_tour_cost": selected_cost,
                "current_aw_best_tour_cost": current_cost,
                "selected_relative_diff_pct": diff_pct,
            }
        )
    base.write_csv(output_dir / "selected_vs_current_aw.csv", comparisons)

    valid_diffs = [row["selected_relative_diff_pct"] for row in comparisons if row["selected_relative_diff_pct"] is not None]
    median_diff = statistics.median(valid_diffs) if len(valid_diffs) == len(manifest["instances"]) else None
    full_feasible_count = sum(row["full_feasible"] for row in metrics)
    signature_count = len({row["cost_signature"] for row in selected})
    selected_feasible = sum(
        audit.feasible_value(row["feasible"]) for row in rows if row["code_hash"] in selected_hashes
    )
    gate = manifest["gate"]
    overall_pass = (
        full_feasible_count >= int(gate["fully_feasible_codes_min"])
        and len(selected) == SELECTED_COUNT
        and selected_feasible == int(gate["selected_coordinates_feasible"])
        and signature_count >= int(gate["selected_cost_signatures_min"])
        and median_diff is not None
        and median_diff <= -float(gate["median_improvement_vs_current_aw_min_pct"])
    )
    selected_payload = [dict(rank=index, **row) for index, row in enumerate(selected, start=1)]
    with (output_dir / "selected_frontier_archive.jsonl").open("w", encoding="utf-8") as handle:
        for row in selected_payload:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "schema_version": "tsp-safe-pool-frontier-summary/v1",
        "study_role": manifest["study_role"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": audit.sha256_file(output_dir / MANIFEST_NAME),
        "coordinates": len(rows),
        "fully_feasible_codes": full_feasible_count,
        "selected_code_hashes": [row["code_hash"] for row in selected],
        "selected_cost_signatures": signature_count,
        "selected_feasible_coordinates": selected_feasible,
        "comparisons": comparisons,
        "median_selected_relative_diff_pct": median_diff,
        "overall_pass": overall_pass,
    }
    audit.write_json(output_dir / "safe_pool_frontier_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def run(output_dir: Path) -> None:
    manifest, catalog_by_hash = load_frozen_inputs(output_dir)
    rows = run_coordinates(output_dir, manifest, catalog_by_hash)
    summarize(output_dir, manifest, rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog-path", type=Path)
    parser.add_argument("--stage-aw-dir", type=Path)
    parser.add_argument("--stage-ax-dir", type=Path)
    args = parser.parse_args()
    if args.command == "prepare" and not all((args.catalog_path, args.stage_aw_dir, args.stage_ax_dir)):
        parser.error("prepare 需要历史目录、Stage AW 和 Stage AX 路径")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(output_dir, args.catalog_path, args.stage_aw_dir, args.stage_ax_dir)
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
