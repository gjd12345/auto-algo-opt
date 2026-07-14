#!/usr/bin/env python3
"""用非 held-out 合成 dev 探针预测历史 TSP 代码的规模安全性。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import audit_tsp_history_scalability as audit


DEV_SIZES = (120, 160, 200)
TARGET_SIZE = 3038
DEV_TIMEOUT_S = 15.0
TARGET_TIMEOUT_S = 30.0
SCALE_SLOT_COUNT = 4
FALSE_SAFE_RATE_MAX = 0.05
RECALL_MIN = 0.50
MANIFEST_NAME = "runtime_probe_manifest.json"
PROBE_FIELDS = (
    "code_hash",
    "objective",
    "original_index",
    "ast_nodes",
    "dev_size",
    "timeout_s",
    "wall_time_s",
    "feasible",
    "error_type",
    "error",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_csv(path: Path, row: dict[str, Any], fields: tuple[str, ...]) -> None:
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("不能写入空 CSV")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_tsplib(path: Path, size: int) -> None:
    """沿用既有探针的固定种子，避免为全池审计另造更容易的新实例。"""
    rng = np.random.default_rng(20260714 + size)
    coords = rng.integers(0, 10001, size=(size, 2))
    lines = [
        f"NAME: synthetic_dev_{size}",
        "TYPE: TSP",
        f"DIMENSION: {size}",
        "EDGE_WEIGHT_TYPE: EUC_2D",
        "NODE_COORD_SECTION",
    ]
    lines.extend(f"{index + 1} {x} {y}" for index, (x, y) in enumerate(coords))
    lines.append("EOF")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_catalog(catalog: list[dict[str, Any]]) -> None:
    hashes = []
    for candidate in catalog:
        code = str(candidate.get("code", ""))
        actual_hash = audit.sha256_bytes(code.encode("utf-8"))
        if candidate.get("code_hash") != actual_hash:
            raise ValueError(f"代码 hash 不匹配：{candidate.get('original_index')}")
        hashes.append(actual_hash)
    if len(hashes) != len(set(hashes)):
        raise ValueError("历史目录包含重复代码")


def prepare(
    output_dir: Path,
    catalog_path: Path,
    label_results_path: Path,
    reference_archive_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"探针清单已存在，禁止覆盖：{manifest_path}")

    catalog_path = catalog_path.resolve()
    label_results_path = label_results_path.resolve()
    reference_archive_path = reference_archive_path.resolve()
    catalog = read_jsonl(catalog_path)
    validate_catalog(catalog)
    for size in DEV_SIZES:
        write_tsplib(output_dir / f"synthetic_dev_{size}.tsp", size)

    manifest = {
        "schema_version": "tsp-runtime-probe-frontier/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "catalog_path": str(catalog_path),
        "catalog_sha256": audit.sha256_file(catalog_path),
        "catalog_count": len(catalog),
        "catalog_code_hashes": [candidate["code_hash"] for candidate in catalog],
        "label_results_path": str(label_results_path),
        "label_results_sha256": audit.sha256_file(label_results_path),
        "reference_archive_path": str(reference_archive_path),
        "reference_archive_sha256": audit.sha256_file(reference_archive_path),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "dev_sizes": DEV_SIZES,
        "dev_timeout_s": DEV_TIMEOUT_S,
        "target_size": TARGET_SIZE,
        "target_timeout_s": TARGET_TIMEOUT_S,
        "scale_slot_count": SCALE_SLOT_COUNT,
        "gate": {
            "selected_false_safe_max": 0,
            "global_false_safe_rate_max": FALSE_SAFE_RATE_MAX,
            "scale_survivor_recall_min": RECALL_MIN,
        },
        "instance_sha256": {
            str(size): audit.sha256_file(output_dir / f"synthetic_dev_{size}.tsp") for size in DEV_SIZES
        },
        "prediction_reads_scale_labels": False,
    }
    audit.write_json(manifest_path, manifest)
    print(json.dumps({"prepared": True, "codes": len(catalog), "coordinates": len(catalog) * len(DEV_SIZES)}, ensure_ascii=False))


def load_frozen_inputs(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    catalog_path = Path(manifest["catalog_path"])
    checks = {
        "catalog_sha256": audit.sha256_file(catalog_path),
        "label_results_sha256": audit.sha256_file(Path(manifest["label_results_path"])),
        "reference_archive_sha256": audit.sha256_file(Path(manifest["reference_archive_path"])),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
    }
    for key, actual in checks.items():
        if manifest[key] != actual:
            raise RuntimeError(f"冻结输入校验失败：{key}")
    for size in manifest["dev_sizes"]:
        instance = output_dir / f"synthetic_dev_{size}.tsp"
        if manifest["instance_sha256"][str(size)] != audit.sha256_file(instance):
            raise RuntimeError(f"合成实例 hash 不匹配：n={size}")

    catalog = read_jsonl(catalog_path)
    validate_catalog(catalog)
    if [candidate["code_hash"] for candidate in catalog] != manifest["catalog_code_hashes"]:
        raise RuntimeError("历史目录顺序或代码集合发生变化")
    return manifest, catalog


def run_probe(output_dir: Path, manifest: dict[str, Any], catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluator = audit.import_evaluator()
    results_path = output_dir / "dev_probe_results.csv"
    rows: list[dict[str, Any]] = read_csv(results_path)
    completed = {(row["code_hash"], int(row["dev_size"])) for row in rows}
    for candidate_index, candidate in enumerate(catalog, start=1):
        for size in manifest["dev_sizes"]:
            key = (candidate["code_hash"], int(size))
            if key in completed:
                continue
            started_at = time.perf_counter()
            result = evaluator(
                candidate["code"],
                str(output_dir / f"synthetic_dev_{size}.tsp"),
                float(manifest["dev_timeout_s"]),
            )
            row = {
                "code_hash": candidate["code_hash"],
                "objective": candidate["objective"],
                "original_index": candidate["original_index"],
                "ast_nodes": candidate["ast_nodes"],
                "dev_size": size,
                "timeout_s": manifest["dev_timeout_s"],
                "wall_time_s": round(time.perf_counter() - started_at, 6),
                "feasible": bool(result.get("feasible", False)),
                "error_type": result.get("error_type", ""),
                "error": result.get("error", ""),
            }
            append_csv(results_path, row, PROBE_FIELDS)
            rows.append(row)
            completed.add(key)
        if candidate_index % 10 == 0 or candidate_index == len(catalog):
            print(json.dumps({"candidate": candidate_index, "coordinates": len(rows)}, ensure_ascii=False), flush=True)
    return rows


def fit_prediction(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["dev_size"]))
    completed = len(ordered) == len(DEV_SIZES) and all(audit.feasible_value(row["feasible"]) for row in ordered)
    exponent = None
    predicted_runtime = None
    predicted_safe = False
    if completed:
        x_values = np.log([int(row["dev_size"]) for row in ordered])
        y_values = np.log([max(float(row["wall_time_s"]), 1e-6) for row in ordered])
        exponent, intercept = np.polyfit(x_values, y_values, 1)
        predicted_runtime = float(np.exp(intercept) * TARGET_SIZE ** exponent)
        predicted_safe = math.isfinite(predicted_runtime) and predicted_runtime < TARGET_TIMEOUT_S
    return {
        "code_hash": candidate["code_hash"],
        "objective": candidate["objective"],
        "original_index": candidate["original_index"],
        "ast_nodes": candidate["ast_nodes"],
        "all_dev_completed": completed,
        "scaling_exponent": float(exponent) if exponent is not None else None,
        "predicted_target_runtime_s": predicted_runtime,
        "predicted_scale_safe": predicted_safe,
    }


def freeze_predictions(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    prediction_path = output_dir / "runtime_predictions_frozen.csv"
    lock_path = output_dir / "runtime_prediction_lock.json"
    if prediction_path.exists() or lock_path.exists():
        if not prediction_path.exists() or not lock_path.exists():
            raise RuntimeError("预测文件与锁文件不完整")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock["prediction_sha256"] != audit.sha256_file(prediction_path):
            raise RuntimeError("冻结预测 hash 不匹配")
        return read_csv(prediction_path), lock["prediction_sha256"]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in probe_rows:
        grouped.setdefault(row["code_hash"], []).append(row)
    predictions = [fit_prediction(candidate, grouped.get(candidate["code_hash"], [])) for candidate in catalog]
    write_csv(prediction_path, predictions)
    prediction_hash = audit.sha256_file(prediction_path)
    audit.write_json(
        lock_path,
        {
            "schema_version": "tsp-runtime-probe-prediction-lock/v1",
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


def bool_value(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def validate_predictions(
    output_dir: Path,
    manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
    prediction_hash: str,
) -> None:
    # 标签直到预测文件和 hash 锁定后才读取，防止用 Core-12 结果调阈值或重排候选。
    label_rows = read_csv(Path(manifest["label_results_path"]))
    full_survivors = {
        row["code_hash"]
        for row in label_rows
        if row["instance"] == "pcb3038" and audit.feasible_value(row["feasible"])
    }
    reference_hashes = {row["code_hash"] for row in read_jsonl(Path(manifest["reference_archive_path"]))}
    validation_rows = []
    for prediction in predictions:
        predicted_safe = bool_value(prediction["predicted_scale_safe"])
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
    write_csv(output_dir / "runtime_probe_validation.csv", validation_rows)

    predicted_safe_rows = [row for row in validation_rows if row["predicted_scale_safe"]]
    selected = sorted(
        predicted_safe_rows,
        key=lambda row: (
            float(row["objective"]),
            float(row["predicted_target_runtime_s"]),
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
        "schema_version": "tsp-runtime-probe-frontier-summary/v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "prediction_sha256": prediction_hash,
        "total": len(validation_rows),
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
    audit.write_json(output_dir / "runtime_probe_summary.json", summary)
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
    parser.add_argument("--label-results", type=Path)
    parser.add_argument("--reference-archive", type=Path)
    args = parser.parse_args()
    if args.command == "prepare" and not all((args.catalog_path, args.label_results, args.reference_archive)):
        parser.error("prepare 需要 --catalog-path、--label-results 和 --reference-archive")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(output_dir, args.catalog_path, args.label_results, args.reference_archive)
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
