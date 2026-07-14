#!/usr/bin/env python3
"""用冻结的 Core-12 合同评估一个 TSP 代码档案。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_tsp_history_scalability as audit


RESULT_FIELDS = (*audit.RESULT_FIELDS, "source")
MANIFEST_NAME = "archive_core12_manifest.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_result(path: Path, row: dict[str, Any]) -> None:
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def validate_archive(candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        raise ValueError("冻结档案不能为空")
    seen = set()
    for candidate in candidates:
        code = str(candidate.get("code", ""))
        expected_hash = audit.sha256_bytes(code.encode("utf-8"))
        if candidate.get("code_hash") != expected_hash:
            raise ValueError(f"代码 hash 不匹配：{candidate.get('code_hash')}")
        if expected_hash in seen:
            raise ValueError(f"冻结档案包含重复代码：{expected_hash}")
        seen.add(expected_hash)


def resolve_archive_candidates(archive_path: Path, catalog_path: Path | None) -> list[dict[str, Any]]:
    archive_rows = read_jsonl(archive_path)
    if not archive_rows:
        raise ValueError("冻结档案不能为空")

    rows_with_code = [bool(str(row.get("code", ""))) for row in archive_rows]
    if all(rows_with_code):
        validate_archive(archive_rows)
        return archive_rows
    if any(rows_with_code):
        raise ValueError("冻结档案不能混合完整代码与仅 hash 记录")
    if catalog_path is None:
        raise ValueError("仅含代码 hash 的冻结档案需要 --catalog-path")

    # 档案只保存筛选结果，完整代码继续由同一份历史目录提供，避免复制代码造成来源漂移。
    catalog = read_jsonl(catalog_path)
    validate_archive(catalog)
    catalog_by_hash = {row["code_hash"]: row for row in catalog}
    archive_hashes = [str(row.get("code_hash", "")) for row in archive_rows]
    if any(not code_hash for code_hash in archive_hashes):
        raise ValueError("冻结档案存在空 code_hash")
    if len(set(archive_hashes)) != len(archive_hashes):
        raise ValueError("冻结档案包含重复 code_hash")
    missing_hashes = [code_hash for code_hash in archive_hashes if code_hash not in catalog_by_hash]
    if missing_hashes:
        raise ValueError(f"历史目录缺少冻结代码：{missing_hashes}")
    return [catalog_by_hash[code_hash] for code_hash in archive_hashes]


def prepare(
    output_dir: Path,
    archive_path: Path,
    reuse_results: Path | None,
    catalog_path: Path | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"评估清单已存在，禁止覆盖：{manifest_path}")

    archive_path = archive_path.resolve()
    catalog_path = catalog_path.resolve() if catalog_path else None
    candidates = resolve_archive_candidates(archive_path, catalog_path)
    registry = audit.load_tsp_registry()
    reuse_path = reuse_results.resolve() if reuse_results else None
    if reuse_path and not reuse_path.is_file():
        raise FileNotFoundError(f"复用结果不存在：{reuse_path}")

    manifest = {
        "schema_version": "tsp-frozen-archive-core12/v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": audit.current_commit(),
        "archive_path": str(archive_path),
        "archive_sha256": audit.sha256_file(archive_path),
        "archive_code_count": len(candidates),
        "archive_code_hashes": [candidate["code_hash"] for candidate in candidates],
        "catalog_path": str(catalog_path) if catalog_path else None,
        "catalog_sha256": audit.sha256_file(catalog_path) if catalog_path else None,
        "registry_sha256": audit.sha256_file(audit.REGISTRY_PATH),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
        "timeout_s": 30.0,
        "serial_execution": True,
        "selection_uses_core12_outcomes": False,
        "reuse_results_path": str(reuse_path) if reuse_path else None,
        "reuse_results_sha256": audit.sha256_file(reuse_path) if reuse_path else None,
        "tsp_instances": registry,
    }
    audit.write_json(manifest_path, manifest)
    print(json.dumps({"prepared": True, "codes": len(candidates), "instances": len(registry)}, ensure_ascii=False))


def load_frozen_inputs(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((output_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    archive_path = Path(manifest["archive_path"])
    checks = {
        "archive_sha256": audit.sha256_file(archive_path),
        "registry_sha256": audit.sha256_file(audit.REGISTRY_PATH),
        "evaluator_sha256": audit.sha256_file(audit.EVALUATOR_PATH),
    }
    reuse_path = Path(manifest["reuse_results_path"]) if manifest.get("reuse_results_path") else None
    catalog_path = Path(manifest["catalog_path"]) if manifest.get("catalog_path") else None
    if reuse_path:
        checks["reuse_results_sha256"] = audit.sha256_file(reuse_path)
    if catalog_path:
        checks["catalog_sha256"] = audit.sha256_file(catalog_path)
    for key, actual in checks.items():
        if manifest[key] != actual:
            raise RuntimeError(f"冻结输入校验失败：{key}")

    candidates = resolve_archive_candidates(archive_path, catalog_path)
    if [candidate["code_hash"] for candidate in candidates] != manifest["archive_code_hashes"]:
        raise RuntimeError("冻结档案顺序或代码集合发生变化")
    return manifest, candidates


def build_reuse_lookup(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    path_value = manifest.get("reuse_results_path")
    if not path_value:
        return {}
    return {(row["code_hash"], row["instance"]): row for row in read_csv(Path(path_value))}


def reused_row(
    source: dict[str, str], candidate: dict[str, Any], stage_index: int, timeout_s: float
) -> dict[str, Any]:
    # 只有代码 hash 与实例都相同才复用；训练分数和来源位置仍以本次冻结档案为准。
    return {
        **source,
        "phase": "archive_core12",
        "stage_index": stage_index,
        "timeout_s": timeout_s,
        "objective": candidate["objective"],
        "original_index": candidate["original_index"],
        "ast_nodes": candidate["ast_nodes"],
        "source": "reused_frozen_result",
    }


def summarize(output_dir: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    per_code = []
    for code_hash in manifest["archive_code_hashes"]:
        current = [row for row in rows if row["code_hash"] == code_hash]
        gaps = [
            float(row["relative_gap_pct"])
            for row in current
            if audit.feasible_value(row["feasible"]) and row["relative_gap_pct"] not in (None, "")
        ]
        per_code.append(
            {
                "code_hash": code_hash,
                "feasible_count": sum(audit.feasible_value(row["feasible"]) for row in current),
                "instance_count": len(current),
                "median_relative_gap_pct": statistics.median(gaps) if gaps else None,
                "reused_count": sum(row.get("source") == "reused_frozen_result" for row in current),
            }
        )
    summary = {
        "schema_version": "tsp-frozen-archive-core12-summary/v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": manifest["repo_commit"],
        "archive_sha256": manifest["archive_sha256"],
        "coordinate_count": len(rows),
        "unique_coordinate_count": len({(row["code_hash"], row["instance"]) for row in rows}),
        "feasible_count": sum(audit.feasible_value(row["feasible"]) for row in rows),
        "timeout_count": sum(row.get("error_type") == "HeldOutTimeout" for row in rows),
        "reused_count": sum(row.get("source") == "reused_frozen_result" for row in rows),
        "per_code": per_code,
    }
    audit.write_json(output_dir / "archive_core12_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def run(output_dir: Path) -> None:
    manifest, candidates = load_frozen_inputs(output_dir)
    evaluator = audit.import_evaluator()
    registry = {item["instance"]: item for item in manifest["tsp_instances"]}
    reuse_lookup = build_reuse_lookup(manifest)
    results_path = output_dir / "archive_core12_results.csv"
    rows: list[dict[str, Any]] = read_csv(results_path)
    completed = {(row["code_hash"], row["instance"]) for row in rows}

    for candidate_index, candidate in enumerate(candidates, start=1):
        for stage_index, (instance, item) in enumerate(registry.items(), start=1):
            key = (candidate["code_hash"], instance)
            if key in completed:
                continue
            if key in reuse_lookup:
                row = reused_row(reuse_lookup[key], candidate, stage_index, float(manifest["timeout_s"]))
            else:
                row = audit.evaluate_coordinate(
                    evaluator,
                    "archive_core12",
                    stage_index,
                    instance,
                    audit.REPO_ROOT / item["path"],
                    float(manifest["timeout_s"]),
                    candidate,
                )
                row["source"] = "new_serial_evaluation"
            append_result(results_path, row)
            rows.append(row)
            completed.add(key)
        print(json.dumps({"candidate": candidate_index, "completed_coordinates": len(rows)}, ensure_ascii=False), flush=True)
    summarize(output_dir, manifest, rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path)
    parser.add_argument("--catalog-path", type=Path)
    parser.add_argument("--reuse-results", type=Path)
    args = parser.parse_args()
    if args.command == "prepare" and args.archive_path is None:
        parser.error("prepare 需要 --archive-path")
    return args


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(output_dir, args.archive_path, args.reuse_results, args.catalog_path)
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
