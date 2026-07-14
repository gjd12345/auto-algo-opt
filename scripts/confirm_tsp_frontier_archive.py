#!/usr/bin/env python3
"""在全新合成实例上确认 TSP 质量速度前沿档案。"""

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
import confirm_tsp_scale_archive as confirmation


INSTANCE_SIZE = 3038
INSTANCE_SEEDS = (20270011, 20270012, 20270013)
TIMEOUT_S = 30.0
ARCHIVE_SIZE = 4
MIN_BETTER_INSTANCES = 2
MIN_MEDIAN_IMPROVEMENT_PCT = 0.1
MANIFEST_NAME = "frontier_archive_confirmation_manifest.json"


def load_selected_hashes(stage_ay_dir: Path) -> list[str]:
    summary_path = stage_ay_dir / "safe_pool_frontier_summary.json"
    archive_path = stage_ay_dir / "selected_frontier_archive.jsonl"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not summary.get("overall_pass"):
        raise RuntimeError("Stage AY 未通过发现门槛，不能进入确认")
    rows = base.read_jsonl(archive_path)
    hashes = [str(row["code_hash"]) for row in rows]
    if len(hashes) != ARCHIVE_SIZE or len(hashes) != len(set(hashes)):
        raise RuntimeError("Stage AY 冻结档案不是四条唯一代码")
    if hashes != [str(value) for value in summary["selected_code_hashes"]]:
        raise RuntimeError("Stage AY summary 与冻结档案顺序不一致")
    return hashes


def prepare(output_dir: Path, catalog_path: Path, stage_ay_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"确认清单已存在，禁止覆盖：{manifest_path}")

    catalog_path = catalog_path.resolve()
    stage_ay_dir = stage_ay_dir.resolve()
    stage_ay_manifest_path = stage_ay_dir / "safe_pool_frontier_manifest.json"
    stage_ay_summary_path = stage_ay_dir / "safe_pool_frontier_summary.json"
    selected_archive_path = stage_ay_dir / "selected_frontier_archive.jsonl"
    stage_ay_manifest = json.loads(stage_ay_manifest_path.read_text(encoding="utf-8"))
    selected_hashes = load_selected_hashes(stage_ay_dir)
    current_aw_hashes = [str(value) for value in stage_ay_manifest["current_aw_archive"]]
    if len(current_aw_hashes) != ARCHIVE_SIZE or len(current_aw_hashes) != len(set(current_aw_hashes)):
        raise RuntimeError("Stage AY 记录的当前 AW 档案不是四条唯一代码")

    catalog = base.read_jsonl(catalog_path)
    base.validate_catalog(catalog)
    catalog_hashes = {row["code_hash"] for row in catalog}
    selected_union = set(selected_hashes) | set(current_aw_hashes)
    if not selected_union <= catalog_hashes:
        raise RuntimeError("确认档案包含历史目录外代码")

    instances = []
    for index, seed in enumerate(INSTANCE_SEEDS, start=1):
        name = f"synthetic_frontier_confirm_{index}_{INSTANCE_SIZE}"
        path = output_dir / f"{name}.tsp"
        confirmation.write_tsplib(path, INSTANCE_SIZE, seed, name)
        instances.append(
            {
                "name": name,
                "path": str(path.resolve()),
                "size": INSTANCE_SIZE,
                "seed": seed,
                "sha256": audit.sha256_file(path),
            }
        )

    candidates = []
    for row in catalog:
        code_hash = row["code_hash"]
        if code_hash not in selected_union:
            continue
        memberships = []
        if code_hash in selected_hashes:
            memberships.append("selected_frontier")
        if code_hash in current_aw_hashes:
            memberships.append("current_aw")
        candidates.append(
            {
                "code_hash": code_hash,
                "objective": row["objective"],
                "original_index": row["original_index"],
                "ast_nodes": row["ast_nodes"],
                "archive_memberships": memberships,
            }
        )

    inputs = {
        "catalog": catalog_path,
        "stage_ay_manifest": stage_ay_manifest_path,
        "stage_ay_summary": stage_ay_summary_path,
        "selected_archive": selected_archive_path,
    }
    manifest = {
        "schema_version": "tsp-frontier-archive-confirmation/v1",
        "study_role": "independent_synthetic_frontier_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "inputs": {
            name: {"path": str(path), "sha256": audit.sha256_file(path)}
            for name, path in inputs.items()
        },
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "archives": {
            "selected_frontier": selected_hashes,
            "current_aw": current_aw_hashes,
        },
        "candidates": candidates,
        "instances": instances,
        "timeout_s": TIMEOUT_S,
        "expected_coordinates": len(candidates) * len(instances),
        "gate": {
            "selected_required_feasible": ARCHIVE_SIZE * len(instances),
            "median_improvement_min_pct": MIN_MEDIAN_IMPROVEMENT_PCT,
            "better_instances_min": MIN_BETTER_INSTANCES,
            "posthoc_slot_replacement_allowed": False,
        },
        "comparison": "每个实例分别取冻结新四槽和当前 AW 四槽中的最低可行路线成本",
    }
    audit.write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "prepared": True,
                "unique_codes": len(candidates),
                "instances": len(instances),
                "coordinates": manifest["expected_coordinates"],
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
        raise RuntimeError("评估器在确认清单冻结后发生变化")
    for instance in manifest["instances"]:
        if audit.sha256_file(Path(instance["path"])) != instance["sha256"]:
            raise RuntimeError(f"确认实例 hash 不匹配：{instance['name']}")

    catalog = base.read_jsonl(Path(manifest["inputs"]["catalog"]["path"]))
    base.validate_catalog(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    if {row["code_hash"] for row in manifest["candidates"]} != set().union(
        *map(set, manifest["archives"].values())
    ):
        raise RuntimeError("冻结确认代码集合不一致")
    return manifest, catalog_by_hash


def result_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["code_hash"]), str(row["instance"])


def run_coordinates(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog_by_hash: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results_path = output_dir / "frontier_archive_confirmation_results.csv"
    rows: list[dict[str, Any]] = base.read_csv(results_path)
    completed = {result_key(row) for row in rows}
    if len(completed) != len(rows):
        raise RuntimeError("确认结果包含重复坐标")

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
            except Exception as exc:  # 冻结候选失败必须原样保留，不能事后换槽。
                result = {
                    "feasible": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            row = {
                **frozen,
                "archive_memberships": "|".join(frozen["archive_memberships"]),
                "instance": instance["name"],
                "instance_seed": instance["seed"],
                "instance_sha256": instance["sha256"],
                "timeout_s": manifest["timeout_s"],
                "wall_time_s": round(time.perf_counter() - started_at, 6),
                "feasible": bool(result.get("feasible", False)),
                "tour_cost": result.get("tour_cost"),
                "error_type": result.get("error_type", ""),
                "error": result.get("error", ""),
            }
            base.append_csv(results_path, row, confirmation.RESULT_FIELDS)
            rows.append(row)
            completed.add(key)
            print(json.dumps({"coordinates": len(rows), "total": total}), flush=True)
    if len(rows) != total:
        raise RuntimeError(f"冻结坐标未完成：{len(rows)}/{total}")
    return rows


def summarize(output_dir: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    summaries = {
        name: confirmation.archive_summary(name, hashes, manifest["instances"], rows)
        for name, hashes in manifest["archives"].items()
    }
    comparisons = []
    for instance in manifest["instances"]:
        name = instance["name"]
        selected_cost = summaries["selected_frontier"]["best_tour_cost_by_instance"][name]
        current_cost = summaries["current_aw"]["best_tour_cost_by_instance"][name]
        if selected_cost is None or current_cost is None:
            diff_pct = None
            direction = "missing"
        else:
            diff_pct = (selected_cost - current_cost) / current_cost * 100.0
            direction = "same"
            if diff_pct < -1e-12:
                direction = "better"
            elif diff_pct > 1e-12:
                direction = "worse"
        comparisons.append(
            {
                "instance": name,
                "selected_best_tour_cost": selected_cost,
                "current_aw_best_tour_cost": current_cost,
                "selected_relative_diff_pct": diff_pct,
                "direction": direction,
            }
        )
    base.write_csv(output_dir / "frontier_vs_current_aw.csv", comparisons)

    valid_diffs = [row["selected_relative_diff_pct"] for row in comparisons if row["selected_relative_diff_pct"] is not None]
    median_diff = statistics.median(valid_diffs) if len(valid_diffs) == len(manifest["instances"]) else None
    selected_hashes = set(manifest["archives"]["selected_frontier"])
    code_validity = {
        code_hash: sum(
            audit.feasible_value(row["feasible"]) for row in rows if row["code_hash"] == code_hash
        )
        for code_hash in manifest["archives"]["selected_frontier"]
    }
    direction_counts = {
        direction: sum(row["direction"] == direction for row in comparisons)
        for direction in ("better", "same", "worse", "missing")
    }
    selected_feasible = sum(
        audit.feasible_value(row["feasible"]) for row in rows if row["code_hash"] in selected_hashes
    )
    gate = manifest["gate"]
    overall_pass = (
        selected_feasible == int(gate["selected_required_feasible"])
        and median_diff is not None
        and median_diff <= -float(gate["median_improvement_min_pct"])
        and direction_counts["better"] >= int(gate["better_instances_min"])
    )
    summary = {
        "schema_version": "tsp-frontier-archive-confirmation-summary/v1",
        "study_role": manifest["study_role"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": audit.sha256_file(output_dir / MANIFEST_NAME),
        "coordinates": len(rows),
        "archives": summaries,
        "selected_code_validity": code_validity,
        "comparisons": comparisons,
        "direction_counts": direction_counts,
        "median_selected_relative_diff_pct": median_diff,
        "overall_pass": overall_pass,
    }
    audit.write_json(output_dir / "frontier_archive_confirmation_summary.json", summary)
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
    parser.add_argument("--stage-ay-dir", type=Path)
    args = parser.parse_args()
    if args.command == "prepare" and not all((args.catalog_path, args.stage_ay_dir)):
        parser.error("prepare 需要历史目录和 Stage AY 路径")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(output_dir, args.catalog_path, args.stage_ay_dir)
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
