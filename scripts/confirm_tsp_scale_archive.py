#!/usr/bin/env python3
"""在全新合成 n=3038 实例上独立确认 TSP 规模档案。"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import audit_tsp_history_scalability as audit
import audit_tsp_runtime_probe_frontier as base


INSTANCE_SIZE = 3038
INSTANCE_SEEDS = (20270001, 20270002, 20270003)
TIMEOUT_S = 30.0
SCALE_SLOT_COUNT = 4
QUALITY_DIAGNOSTIC_COUNT = 2
MEDIAN_COST_DIFF_MAX_PCT = 2.0
MANIFEST_NAME = "scale_archive_confirmation_manifest.json"
RESULT_FIELDS = (
    "code_hash",
    "objective",
    "original_index",
    "ast_nodes",
    "archive_memberships",
    "instance",
    "instance_seed",
    "instance_sha256",
    "timeout_s",
    "wall_time_s",
    "feasible",
    "tour_cost",
    "error_type",
    "error",
)


def write_tsplib(path: Path, size: int, seed: int, instance_name: str) -> None:
    """用新种子生成固定实例；实例先落盘并冻结 hash，避免运行后改题。"""
    rng = np.random.default_rng(seed)
    coords = rng.integers(0, 10001, size=(size, 2))
    lines = [
        f"NAME: {instance_name}",
        "TYPE: TSP",
        f"DIMENSION: {size}",
        "EDGE_WEIGHT_TYPE: EUC_2D",
        "NODE_COORD_SECTION",
    ]
    lines.extend(f"{index + 1} {x} {y}" for index, (x, y) in enumerate(coords))
    lines.append("EOF")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_archive_hashes(path: Path, count: int) -> list[str]:
    rows = base.read_jsonl(path)
    if len(rows) < count:
        raise ValueError(f"档案不足 {count} 条：{path}")
    hashes = [str(row["code_hash"]) for row in rows[:count]]
    if len(hashes) != len(set(hashes)):
        raise ValueError(f"档案前 {count} 条包含重复代码：{path}")
    return hashes


def prepare(
    output_dir: Path,
    catalog_path: Path,
    stage_aw_dir: Path,
    scale_archive_path: Path,
    quality_archive_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"确认清单已存在，禁止覆盖：{manifest_path}")

    paths = {
        "catalog": catalog_path.resolve(),
        "stage_aw_summary": (stage_aw_dir.resolve() / "direct_scale_probe_summary.json"),
        "scale_archive": scale_archive_path.resolve(),
        "quality_archive": quality_archive_path.resolve(),
    }
    catalog = base.read_jsonl(paths["catalog"])
    base.validate_catalog(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    stage_aw_summary = json.loads(paths["stage_aw_summary"].read_text(encoding="utf-8"))
    if not stage_aw_summary.get("overall_pass"):
        raise RuntimeError("Stage AW 未通过冻结门槛，不能进入独立确认")

    archives = {
        "aw_scale": [str(value) for value in stage_aw_summary["selected_scale_slots"]],
        "reference_scale": read_archive_hashes(paths["scale_archive"], SCALE_SLOT_COUNT),
        "quality_diagnostic": read_archive_hashes(paths["quality_archive"], QUALITY_DIAGNOSTIC_COUNT),
    }
    if len(archives["aw_scale"]) != SCALE_SLOT_COUNT:
        raise ValueError("Stage AW 规模档案不是四槽")
    selected_hashes = set().union(*map(set, archives.values()))
    if not selected_hashes <= set(catalog_by_hash):
        raise ValueError("档案包含历史目录中不存在的代码")

    instances = []
    for index, seed in enumerate(INSTANCE_SEEDS, start=1):
        instance_name = f"synthetic_confirm_{index}_{INSTANCE_SIZE}"
        instance_path = output_dir / f"{instance_name}.tsp"
        write_tsplib(instance_path, INSTANCE_SIZE, seed, instance_name)
        instances.append(
            {
                "name": instance_name,
                "path": str(instance_path.resolve()),
                "size": INSTANCE_SIZE,
                "seed": seed,
                "sha256": audit.sha256_file(instance_path),
            }
        )

    candidates = []
    for row in catalog:
        code_hash = row["code_hash"]
        if code_hash not in selected_hashes:
            continue
        memberships = [name for name, hashes in archives.items() if code_hash in hashes]
        candidates.append(
            {
                "code_hash": code_hash,
                "objective": row["objective"],
                "original_index": row["original_index"],
                "ast_nodes": row["ast_nodes"],
                "archive_memberships": memberships,
            }
        )

    manifest = {
        "schema_version": "tsp-scale-archive-confirmation/v1",
        "study_role": "independent_synthetic_target_scale_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "inputs": {
            name: {"path": str(path), "sha256": audit.sha256_file(path)}
            for name, path in paths.items()
        },
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "archives": archives,
        "candidates": candidates,
        "instances": instances,
        "timeout_s": TIMEOUT_S,
        "expected_coordinates": len(candidates) * len(instances),
        "gate": {
            "aw_scale_required_feasible": SCALE_SLOT_COUNT * len(instances),
            "median_best_cost_diff_max_pct": MEDIAN_COST_DIFF_MAX_PCT,
            "quality_diagnostic_affects_gate": False,
        },
        "comparison": "每个实例分别取 AW 四槽和参考四槽中的最低可行路线成本",
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
        raise RuntimeError("评估器在清单冻结后发生变化")
    for instance in manifest["instances"]:
        if audit.sha256_file(Path(instance["path"])) != instance["sha256"]:
            raise RuntimeError(f"实例 hash 不匹配：{instance['name']}")

    catalog = base.read_jsonl(Path(manifest["inputs"]["catalog"]["path"]))
    base.validate_catalog(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    frozen_hashes = {row["code_hash"] for row in manifest["candidates"]}
    if not frozen_hashes <= set(catalog_by_hash):
        raise RuntimeError("冻结代码不在当前历史目录中")
    return manifest, catalog_by_hash


def result_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["code_hash"]), str(row["instance"])


def run_coordinates(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog_by_hash: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    results_path = output_dir / "scale_archive_confirmation_results.csv"
    rows: list[dict[str, Any]] = base.read_csv(results_path)
    completed = {result_key(row) for row in rows}
    if len(completed) != len(rows):
        raise RuntimeError("结果中存在重复坐标")

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
            except Exception as exc:  # 单个候选失败不应丢掉其余冻结坐标。
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
            base.append_csv(results_path, row, RESULT_FIELDS)
            rows.append(row)
            completed.add(key)
            print(json.dumps({"coordinates": len(rows), "total": total}), flush=True)
    if len(rows) != total:
        raise RuntimeError(f"冻结坐标未完成：{len(rows)}/{total}")
    return rows


def archive_summary(
    archive_name: str,
    hashes: list[str],
    instances: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = [row for row in rows if row["code_hash"] in hashes]
    best_by_instance: dict[str, float | None] = {}
    for instance in instances:
        costs = [
            float(row["tour_cost"])
            for row in selected
            if row["instance"] == instance["name"]
            and audit.feasible_value(row["feasible"])
            and row.get("tour_cost") not in (None, "")
        ]
        best_by_instance[instance["name"]] = min(costs) if costs else None
    return {
        "archive": archive_name,
        "codes": len(hashes),
        "coordinates": len(selected),
        "feasible": sum(audit.feasible_value(row["feasible"]) for row in selected),
        "best_tour_cost_by_instance": best_by_instance,
    }


def summarize(output_dir: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    summaries = {
        name: archive_summary(name, hashes, manifest["instances"], rows)
        for name, hashes in manifest["archives"].items()
    }
    comparisons = []
    for instance in manifest["instances"]:
        name = instance["name"]
        aw_cost = summaries["aw_scale"]["best_tour_cost_by_instance"][name]
        reference_cost = summaries["reference_scale"]["best_tour_cost_by_instance"][name]
        if aw_cost is None or reference_cost is None:
            diff_pct = None
            direction = "missing"
        else:
            diff_pct = (aw_cost - reference_cost) / reference_cost * 100.0
            direction = "same"
            if diff_pct < -1e-12:
                direction = "better"
            elif diff_pct > 1e-12:
                direction = "worse"
        comparisons.append(
            {
                "instance": name,
                "aw_best_tour_cost": aw_cost,
                "reference_best_tour_cost": reference_cost,
                "aw_relative_diff_pct": diff_pct,
                "direction": direction,
            }
        )
    base.write_csv(output_dir / "scale_archive_cost_comparison.csv", comparisons)

    valid_diffs = [row["aw_relative_diff_pct"] for row in comparisons if row["aw_relative_diff_pct"] is not None]
    median_diff = statistics.median(valid_diffs) if len(valid_diffs) == len(manifest["instances"]) else None
    aw_feasible = summaries["aw_scale"]["feasible"]
    gate = manifest["gate"]
    overall_pass = (
        aw_feasible == int(gate["aw_scale_required_feasible"])
        and median_diff is not None
        and median_diff <= float(gate["median_best_cost_diff_max_pct"])
    )
    summary = {
        "schema_version": "tsp-scale-archive-confirmation-summary/v1",
        "study_role": manifest["study_role"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": audit.sha256_file(output_dir / MANIFEST_NAME),
        "coordinates": len(rows),
        "archives": summaries,
        "comparisons": comparisons,
        "aw_vs_reference_direction_counts": {
            direction: sum(row["direction"] == direction for row in comparisons)
            for direction in ("better", "same", "worse", "missing")
        },
        "median_aw_relative_diff_pct": median_diff,
        "overall_pass": overall_pass,
    }
    audit.write_json(output_dir / "scale_archive_confirmation_summary.json", summary)
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
    parser.add_argument("--scale-archive", type=Path)
    parser.add_argument("--quality-archive", type=Path)
    args = parser.parse_args()
    required = (args.catalog_path, args.stage_aw_dir, args.scale_archive, args.quality_archive)
    if args.command == "prepare" and not all(required):
        parser.error("prepare 需要目录、Stage AW、规模档案和质量档案路径")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(
            output_dir,
            args.catalog_path,
            args.stage_aw_dir,
            args.scale_archive,
            args.quality_archive,
        )
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
