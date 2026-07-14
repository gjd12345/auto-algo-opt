#!/usr/bin/env python3
"""在固定非 held-out 合成 n=3038 上直接检查 TSP 历史代码。"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_tsp_history_scalability as audit
import audit_tsp_runtime_probe_frontier as base


DEV_SIZE = 3038
DEV_TIMEOUT_S = 30.0
SCALE_SLOT_COUNT = 4
FALSE_SAFE_RATE_MAX = 0.05
RECALL_MIN = 0.50
MANIFEST_NAME = "direct_scale_probe_manifest.json"


def load_stage_av_predictions(stage_av_dir: Path) -> list[dict[str, str]]:
    prediction_path = stage_av_dir / "runtime_predictions_frozen.csv"
    lock_path = stage_av_dir / "runtime_prediction_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock["prediction_sha256"] != audit.sha256_file(prediction_path):
        raise RuntimeError("Stage AV 冻结预测 hash 不匹配")
    if lock.get("labels_loaded") is not False:
        raise RuntimeError("Stage AV 预测锁缺少 labels_loaded=false 声明")
    return base.read_csv(prediction_path)


def prepare(
    output_dir: Path,
    catalog_path: Path,
    stage_av_dir: Path,
    label_results_path: Path,
    reference_archive_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"直接探针清单已存在，禁止覆盖：{manifest_path}")

    catalog_path = catalog_path.resolve()
    stage_av_dir = stage_av_dir.resolve()
    label_results_path = label_results_path.resolve()
    reference_archive_path = reference_archive_path.resolve()
    catalog = base.read_jsonl(catalog_path)
    base.validate_catalog(catalog)
    stage_av_predictions = load_stage_av_predictions(stage_av_dir)
    eligible_hashes = [
        row["code_hash"]
        for row in stage_av_predictions
        if base.bool_value(row["predicted_scale_safe"])
    ]
    catalog_hashes = {candidate["code_hash"] for candidate in catalog}
    if len(eligible_hashes) != len(set(eligible_hashes)) or not set(eligible_hashes) <= catalog_hashes:
        raise ValueError("Stage AV 候选集合包含重复或未知代码")

    instance_path = output_dir / f"synthetic_dev_{DEV_SIZE}.tsp"
    base.write_tsplib(instance_path, DEV_SIZE)
    manifest = {
        "schema_version": "tsp-direct-scale-probe/v1",
        "study_role": "adaptive_exploratory_direct_target_scale",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "catalog_path": str(catalog_path),
        "catalog_sha256": audit.sha256_file(catalog_path),
        "catalog_count": len(catalog),
        "catalog_code_hashes": [candidate["code_hash"] for candidate in catalog],
        "stage_av_dir": str(stage_av_dir),
        "stage_av_prediction_sha256": audit.sha256_file(stage_av_dir / "runtime_predictions_frozen.csv"),
        "eligible_code_hashes": eligible_hashes,
        "label_results_path": str(label_results_path),
        "label_results_sha256": audit.sha256_file(label_results_path),
        "reference_archive_path": str(reference_archive_path),
        "reference_archive_sha256": audit.sha256_file(reference_archive_path),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "dev_size": DEV_SIZE,
        "dev_timeout_s": DEV_TIMEOUT_S,
        "scale_slot_count": SCALE_SLOT_COUNT,
        "gate": {
            "selected_false_safe_max": 0,
            "global_false_safe_rate_max": FALSE_SAFE_RATE_MAX,
            "scale_survivor_recall_min": RECALL_MIN,
        },
        "instance_sha256": audit.sha256_file(instance_path),
        "prediction_reads_scale_labels": False,
        "selection_rule": "Stage AV 判安全且合成 n=3038 在 30 秒内可行",
    }
    audit.write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "prepared": True,
                "codes": len(catalog),
                "eligible": len(eligible_hashes),
                "new_coordinates": len(eligible_hashes),
            },
            ensure_ascii=False,
        )
    )


def load_frozen_inputs(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    checks = {
        "catalog_sha256": audit.sha256_file(Path(manifest["catalog_path"])),
        "stage_av_prediction_sha256": audit.sha256_file(
            Path(manifest["stage_av_dir"]) / "runtime_predictions_frozen.csv"
        ),
        "label_results_sha256": audit.sha256_file(Path(manifest["label_results_path"])),
        "reference_archive_sha256": audit.sha256_file(Path(manifest["reference_archive_path"])),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "instance_sha256": audit.sha256_file(output_dir / f"synthetic_dev_{DEV_SIZE}.tsp"),
    }
    for key, actual in checks.items():
        if manifest[key] != actual:
            raise RuntimeError(f"冻结输入校验失败：{key}")

    catalog = base.read_jsonl(Path(manifest["catalog_path"]))
    base.validate_catalog(catalog)
    if [candidate["code_hash"] for candidate in catalog] != manifest["catalog_code_hashes"]:
        raise RuntimeError("历史目录顺序或代码集合发生变化")
    return manifest, catalog


def run_probe(output_dir: Path, manifest: dict[str, Any], catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluator = audit.import_evaluator()
    results_path = output_dir / "dev_probe_results.csv"
    rows: list[dict[str, Any]] = base.read_csv(results_path)
    completed = {row["code_hash"] for row in rows}
    eligible = set(manifest["eligible_code_hashes"])
    candidates = [candidate for candidate in catalog if candidate["code_hash"] in eligible]
    for candidate_index, candidate in enumerate(candidates, start=1):
        if candidate["code_hash"] in completed:
            continue
        started_at = time.perf_counter()
        result = evaluator(
            candidate["code"],
            str(output_dir / f"synthetic_dev_{DEV_SIZE}.tsp"),
            float(manifest["dev_timeout_s"]),
        )
        row = {
            "code_hash": candidate["code_hash"],
            "objective": candidate["objective"],
            "original_index": candidate["original_index"],
            "ast_nodes": candidate["ast_nodes"],
            "dev_size": DEV_SIZE,
            "timeout_s": manifest["dev_timeout_s"],
            "wall_time_s": round(time.perf_counter() - started_at, 6),
            "feasible": bool(result.get("feasible", False)),
            "error_type": result.get("error_type", ""),
            "error": result.get("error", ""),
        }
        base.append_csv(results_path, row, base.PROBE_FIELDS)
        rows.append(row)
        completed.add(candidate["code_hash"])
        if candidate_index % 10 == 0 or candidate_index == len(candidates):
            print(json.dumps({"candidate": candidate_index, "coordinates": len(rows)}), flush=True)
    return rows


def freeze_predictions(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    prediction_path = output_dir / "direct_scale_predictions_frozen.csv"
    lock_path = output_dir / "direct_scale_prediction_lock.json"
    if prediction_path.exists() or lock_path.exists():
        if not prediction_path.exists() or not lock_path.exists():
            raise RuntimeError("预测文件与锁文件不完整")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock["prediction_sha256"] != audit.sha256_file(prediction_path):
            raise RuntimeError("冻结预测 hash 不匹配")
        return base.read_csv(prediction_path), lock["prediction_sha256"]

    stage_av_predictions = {
        row["code_hash"]: row for row in load_stage_av_predictions(Path(manifest["stage_av_dir"]))
    }
    result_by_hash = {row["code_hash"]: row for row in probe_rows}
    predictions = []
    for candidate in catalog:
        stage_av_safe = base.bool_value(stage_av_predictions[candidate["code_hash"]]["predicted_scale_safe"])
        probe = result_by_hash.get(candidate["code_hash"])
        predicted_safe = bool(stage_av_safe and probe and audit.feasible_value(probe["feasible"]))
        reason = "direct_dev_safe" if predicted_safe else "stage_av_reject"
        if stage_av_safe and not predicted_safe:
            reason = "direct_dev_failed"
        predictions.append(
            {
                "code_hash": candidate["code_hash"],
                "objective": candidate["objective"],
                "original_index": candidate["original_index"],
                "ast_nodes": candidate["ast_nodes"],
                "direct_probe_reason": reason,
                "direct_runtime_s": float(probe["wall_time_s"]) if probe else None,
                "predicted_scale_safe": predicted_safe,
            }
        )
    base.write_csv(prediction_path, predictions)
    prediction_hash = audit.sha256_file(prediction_path)
    audit.write_json(
        lock_path,
        {
            "schema_version": "tsp-direct-scale-probe-prediction-lock/v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": audit.sha256_file(output_dir / MANIFEST_NAME),
            "probe_results_sha256": audit.sha256_file(output_dir / "dev_probe_results.csv"),
            "prediction_sha256": prediction_hash,
            "predicted_safe_count": sum(bool(row["predicted_scale_safe"]) for row in predictions),
            "labels_loaded": False,
        },
    )
    print(json.dumps({"prediction_sha256": prediction_hash}, ensure_ascii=False), flush=True)
    return predictions, prediction_hash


def validate_predictions(
    output_dir: Path,
    manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
    prediction_hash: str,
) -> None:
    # 真实 pcb3038 标签只能在直接 dev 结果和预测 hash 冻结后加载。
    label_rows = base.read_csv(Path(manifest["label_results_path"]))
    full_survivors = {
        row["code_hash"]
        for row in label_rows
        if row["instance"] == "pcb3038" and audit.feasible_value(row["feasible"])
    }
    reference_hashes = {
        row["code_hash"] for row in base.read_jsonl(Path(manifest["reference_archive_path"]))
    }
    validation_rows = []
    for prediction in predictions:
        predicted_safe = base.bool_value(prediction["predicted_scale_safe"])
        actual_safe = prediction["code_hash"] in full_survivors
        validation_rows.append(
            {
                **prediction,
                "predicted_scale_safe": predicted_safe,
                "strict_ladder_survivor": actual_safe,
                "correct": predicted_safe == actual_safe,
                "false_safe": predicted_safe and not actual_safe,
                "false_risk": (not predicted_safe) and actual_safe,
                "in_reference_scale_archive": prediction["code_hash"] in reference_hashes,
            }
        )
    base.write_csv(output_dir / "direct_scale_validation.csv", validation_rows)

    predicted_safe_rows = [row for row in validation_rows if row["predicted_scale_safe"]]
    selected = sorted(
        predicted_safe_rows,
        key=lambda row: (
            float(row["objective"]),
            float(row["direct_runtime_s"]),
            int(row["ast_nodes"]),
            int(row["original_index"]),
        ),
    )[: int(manifest["scale_slot_count"])]
    false_safe_count = sum(row["false_safe"] for row in validation_rows)
    false_safe_rate = false_safe_count / len(predicted_safe_rows) if predicted_safe_rows else 1.0
    recall = (
        sum(row["predicted_scale_safe"] and row["strict_ladder_survivor"] for row in validation_rows)
        / len(full_survivors)
        if full_survivors
        else 0.0
    )
    selected_false_safe = sum(row["false_safe"] for row in selected)
    gate = manifest["gate"]
    overall_pass = (
        len(selected) == int(manifest["scale_slot_count"])
        and selected_false_safe <= int(gate["selected_false_safe_max"])
        and false_safe_rate <= float(gate["global_false_safe_rate_max"])
        and recall >= float(gate["scale_survivor_recall_min"])
    )
    summary = {
        "schema_version": "tsp-direct-scale-probe-summary/v1",
        "study_role": manifest["study_role"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "prediction_sha256": prediction_hash,
        "total": len(validation_rows),
        "stage_av_eligible": len(manifest["eligible_code_hashes"]),
        "actual_scale_survivors": len(full_survivors),
        "predicted_safe": len(predicted_safe_rows),
        "correct": sum(row["correct"] for row in validation_rows),
        "false_safe": false_safe_count,
        "false_risk": sum(row["false_risk"] for row in validation_rows),
        "false_safe_rate": false_safe_rate,
        "scale_survivor_recall": recall,
        "selected_scale_slots": [row["code_hash"] for row in selected],
        "selected_false_safe": selected_false_safe,
        "selected_reference_overlap": sum(row["in_reference_scale_archive"] for row in selected),
        "overall_pass": overall_pass,
    }
    audit.write_json(output_dir / "direct_scale_probe_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def run(output_dir: Path) -> None:
    manifest, catalog = load_frozen_inputs(output_dir)
    probe_rows = run_probe(output_dir, manifest, catalog)
    predictions, prediction_hash = freeze_predictions(output_dir, manifest, catalog, probe_rows)
    validate_predictions(output_dir, manifest, predictions, prediction_hash)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog-path", type=Path)
    parser.add_argument("--stage-av-dir", type=Path)
    parser.add_argument("--label-results", type=Path)
    parser.add_argument("--reference-archive", type=Path)
    args = parser.parse_args()
    required = (args.catalog_path, args.stage_av_dir, args.label_results, args.reference_archive)
    if args.command == "prepare" and not all(required):
        parser.error("prepare 需要完整的历史目录、Stage AV、标签和参考档案路径")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(
            output_dir,
            args.catalog_path,
            args.stage_av_dir,
            args.label_results,
            args.reference_archive,
        )
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
