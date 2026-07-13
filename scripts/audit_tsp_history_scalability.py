#!/usr/bin/env python3
"""审计历史 TSP 代码的质量与规模适应性，并冻结双档案。"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "evidence/final_batch_20260630/shared_pool_snapshot/best_codes_tsp_construct.jsonl"
REGISTRY_PATH = REPO_ROOT / "eoh_rag_workspace/experiments/manifests/core_benchmark_registry.json"
EVALUATOR_PATH = REPO_ROOT / "official_eoh/examples/tsp_construct/prob_broad.py"
LADDER = (
    {"instance": "kroA200", "timeout_s": 5.0},
    {"instance": "a280", "timeout_s": 10.0},
    {"instance": "pr1002", "timeout_s": 15.0},
    {"instance": "pcb3038", "timeout_s": 30.0},
)
ARCHIVE_SIZE = 6
RESULT_FIELDS = (
    "phase",
    "stage_index",
    "instance",
    "timeout_s",
    "code_hash",
    "objective",
    "original_index",
    "ast_nodes",
    "wall_time_s",
    "feasible",
    "relative_gap_pct",
    "tour_cost",
    "error_type",
    "error",
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_csv(path: Path, row: dict[str, Any]) -> None:
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def code_metrics(code: str) -> dict[str, Any]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {
            "ast_nodes": None,
            "loop_nodes": None,
            "branch_nodes": None,
            "nonempty_lines": sum(bool(line.strip()) for line in code.splitlines()),
            "parse_error": f"{type(exc).__name__}: {exc}",
        }
    nodes = list(ast.walk(tree))
    return {
        "ast_nodes": len(nodes),
        "loop_nodes": sum(isinstance(node, (ast.For, ast.While)) for node in nodes),
        "branch_nodes": sum(isinstance(node, ast.If) for node in nodes),
        "nonempty_lines": sum(bool(line.strip()) for line in code.splitlines()),
        "parse_error": "",
    }


def load_history_catalog() -> tuple[list[dict[str, Any]], int]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    total_rows = 0
    for original_index, line in enumerate(HISTORY_PATH.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        total_rows += 1
        record = json.loads(line)
        code = str(record["code"])
        code_hash = sha256_bytes(code.encode("utf-8"))
        grouped.setdefault(code_hash, []).append(
            {
                "original_index": original_index,
                "objective": float(record["objective"]),
                "timestamp": record.get("ts"),
                "code": code,
            }
        )

    catalog = []
    for code_hash, occurrences in grouped.items():
        # 同一代码可能被多次写入历史池；保留其最好目标值，并完整记录来源位置。
        canonical = min(occurrences, key=lambda item: (item["objective"], item["original_index"]))
        catalog.append(
            {
                "code_hash": code_hash,
                **canonical,
                **code_metrics(canonical["code"]),
                "occurrence_count": len(occurrences),
                "all_original_indices": [item["original_index"] for item in occurrences],
                "all_objectives": [item["objective"] for item in occurrences],
            }
        )
    catalog.sort(key=lambda item: item["original_index"])
    return catalog, total_rows


def load_tsp_registry() -> list[dict[str, Any]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return [item for item in registry["instances"] if item["problem"] == "tsp_construct"]


def current_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, encoding="utf-8"
    ).strip()


def prepare(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "audit_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"审计清单已存在，禁止覆盖：{manifest_path}")

    catalog, total_rows = load_history_catalog()
    registry = load_tsp_registry()
    catalog_path = output_dir / "history_code_catalog.jsonl"
    with catalog_path.open("w", encoding="utf-8") as handle:
        for item in catalog:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    catalog_csv_fields = (
        "code_hash",
        "original_index",
        "objective",
        "timestamp",
        "ast_nodes",
        "loop_nodes",
        "branch_nodes",
        "nonempty_lines",
        "parse_error",
        "occurrence_count",
        "all_original_indices",
        "all_objectives",
    )
    with (output_dir / "history_code_catalog.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=catalog_csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(catalog)

    manifest = {
        "schema_version": "tsp-history-scalability-audit/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": current_commit(),
        "history_path": str(HISTORY_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "history_sha256": sha256_file(HISTORY_PATH),
        "history_row_count": total_rows,
        "unique_code_count": len(catalog),
        "catalog_sha256": sha256_file(catalog_path),
        "registry_sha256": sha256_file(REGISTRY_PATH),
        "evaluator_sha256": sha256_file(EVALUATOR_PATH),
        "ladder": list(LADDER),
        "archive_size": ARCHIVE_SIZE,
        "quality_archive_rule": "objective asc, original_index asc",
        "scalability_archive_rule": "pass all ladder stages; objective asc, pcb3038 wall time asc, AST nodes asc, original_index asc",
        "ladder_entry_selection_uses_evaluation_outcomes": False,
        "scalability_archive_uses_ladder_outcomes": True,
        "full_core12_rule": "only the frozen scalability archive; 30 seconds per instance; ladder coordinates are reused",
        "tsp_instances": registry,
    }
    write_json(manifest_path, manifest)
    print(json.dumps({"prepared": True, "rows": total_rows, "unique": len(catalog)}, ensure_ascii=False))


def load_frozen_inputs(output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    manifest = json.loads((output_dir / "audit_manifest.json").read_text(encoding="utf-8"))
    checks = {
        "history_sha256": sha256_file(HISTORY_PATH),
        "catalog_sha256": sha256_file(output_dir / "history_code_catalog.jsonl"),
        "registry_sha256": sha256_file(REGISTRY_PATH),
        "evaluator_sha256": sha256_file(EVALUATOR_PATH),
    }
    for key, current_value in checks.items():
        if manifest[key] != current_value:
            raise RuntimeError(f"冻结输入校验失败：{key}")

    catalog = [
        json.loads(line)
        for line in (output_dir / "history_code_catalog.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    registry = {item["instance"]: item for item in manifest["tsp_instances"]}
    return manifest, catalog, registry


def import_evaluator():
    example_dir = REPO_ROOT / "official_eoh/examples/tsp_construct"
    sys.path.insert(0, str(example_dir))
    from prob_broad import evaluate_held_out_with_timeout  # pylint: disable=import-outside-toplevel

    return evaluate_held_out_with_timeout


def result_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row["phase"]), str(row["code_hash"]), str(row["instance"])


def evaluate_coordinate(
    evaluator,
    phase: str,
    stage_index: int,
    instance: str,
    entry: Path,
    timeout_s: float,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        result = evaluator(candidate["code"], str(entry), timeout_s)
    except Exception as exc:  # 单个坏坐标不能中断 206 条历史代码的完整审计。
        result = {
            "feasible": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {
        "phase": phase,
        "stage_index": stage_index,
        "instance": instance,
        "timeout_s": timeout_s,
        "code_hash": candidate["code_hash"],
        "objective": candidate["objective"],
        "original_index": candidate["original_index"],
        "ast_nodes": candidate["ast_nodes"],
        "wall_time_s": round(time.perf_counter() - started_at, 6),
        "feasible": bool(result.get("feasible", False)),
        "relative_gap_pct": result.get("relative_gap_pct"),
        "tour_cost": result.get("tour_cost"),
        "error_type": result.get("error_type", ""),
        "error": result.get("error", ""),
    }


def stage_rows(rows: Iterable[dict[str, Any]], phase: str, instance: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["phase"] == phase and row["instance"] == instance]


def feasible_value(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def write_stage_summary(output_dir: Path, rows: list[dict[str, Any]], catalog_count: int) -> None:
    stages = []
    for stage_index, stage in enumerate(LADDER, start=1):
        current = stage_rows(rows, "ladder", stage["instance"])
        stages.append(
            {
                "stage_index": stage_index,
                "instance": stage["instance"],
                "timeout_s": stage["timeout_s"],
                "evaluated": len(current),
                "feasible": sum(feasible_value(row["feasible"]) for row in current),
                "timeout": sum(row.get("error_type") == "HeldOutTimeout" for row in current),
            }
        )
    write_json(output_dir / "ladder_progress.json", {"catalog_count": catalog_count, "stages": stages})


def run_ladder(
    output_dir: Path,
    catalog: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    evaluator,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results_path = output_dir / "ladder_results.csv"
    rows: list[dict[str, Any]] = read_csv(results_path)
    completed = {result_key(row) for row in rows}
    candidates = list(catalog)

    for stage_index, stage in enumerate(LADDER, start=1):
        instance = stage["instance"]
        entry = REPO_ROOT / registry[instance]["path"]
        for candidate in candidates:
            key = ("ladder", candidate["code_hash"], instance)
            if key in completed:
                continue
            row = evaluate_coordinate(
                evaluator,
                "ladder",
                stage_index,
                instance,
                entry,
                float(stage["timeout_s"]),
                candidate,
            )
            append_csv(results_path, row)
            rows.append(row)
            completed.add(key)

        current = {row["code_hash"]: row for row in stage_rows(rows, "ladder", instance)}
        candidates = [candidate for candidate in candidates if feasible_value(current[candidate["code_hash"]]["feasible"])]
        write_stage_summary(output_dir, rows, len(catalog))
        print(json.dumps({"stage": instance, "survivors": len(candidates)}, ensure_ascii=False), flush=True)
        if not candidates:
            break
    return rows, candidates


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def pareto_frontier(candidates: list[dict[str, Any]], final_runtime: dict[str, float]) -> list[dict[str, Any]]:
    frontier = []
    for candidate in candidates:
        point = (
            float(candidate["objective"]),
            final_runtime[candidate["code_hash"]],
            float(candidate["ast_nodes"] or float("inf")),
        )
        dominated = False
        for other in candidates:
            if other["code_hash"] == candidate["code_hash"]:
                continue
            other_point = (
                float(other["objective"]),
                final_runtime[other["code_hash"]],
                float(other["ast_nodes"] or float("inf")),
            )
            if all(left <= right for left, right in zip(other_point, point)) and any(
                left < right for left, right in zip(other_point, point)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append({**candidate, "pcb3038_wall_time_s": final_runtime[candidate["code_hash"]]})
    return sorted(frontier, key=lambda item: (item["objective"], item["pcb3038_wall_time_s"], item["ast_nodes"] or 10**9))


def freeze_archives(
    output_dir: Path,
    catalog: list[dict[str, Any]],
    ladder_rows: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    quality_archive = sorted(catalog, key=lambda item: (item["objective"], item["original_index"]))[:ARCHIVE_SIZE]
    final_runtime = {
        row["code_hash"]: float(row["wall_time_s"])
        for row in stage_rows(ladder_rows, "ladder", LADDER[-1]["instance"])
        if feasible_value(row["feasible"])
    }
    scalability_archive = sorted(
        survivors,
        key=lambda item: (
            item["objective"],
            final_runtime[item["code_hash"]],
            item["ast_nodes"] or 10**9,
            item["original_index"],
        ),
    )[:ARCHIVE_SIZE]

    quality_path = output_dir / "quality_archive.jsonl"
    scalability_path = output_dir / "scalability_archive.jsonl"
    frontier_path = output_dir / "scalable_pareto_frontier.jsonl"
    write_jsonl(quality_path, quality_archive)
    write_jsonl(scalability_path, scalability_archive)
    write_jsonl(frontier_path, pareto_frontier(survivors, final_runtime))
    write_json(
        output_dir / "archive_hashes.json",
        {
            "quality_archive_sha256": sha256_file(quality_path),
            "scalability_archive_sha256": sha256_file(scalability_path),
            "scalable_pareto_frontier_sha256": sha256_file(frontier_path),
        },
    )
    return quality_archive, scalability_archive


def run_core12(
    output_dir: Path,
    archive: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    ladder_rows: list[dict[str, Any]],
    evaluator,
) -> list[dict[str, Any]]:
    results_path = output_dir / "scalability_archive_core12_results.csv"
    rows: list[dict[str, Any]] = read_csv(results_path)
    completed = {result_key(row) for row in rows}
    ladder_lookup = {
        (row["code_hash"], row["instance"]): row
        for row in ladder_rows
        if row["phase"] == "ladder"
    }
    for candidate in archive:
        for stage_index, (instance, item) in enumerate(registry.items(), start=1):
            key = ("core12", candidate["code_hash"], instance)
            if key in completed:
                continue
            if (candidate["code_hash"], instance) in ladder_lookup:
                source = ladder_lookup[(candidate["code_hash"], instance)]
                row = {**source, "phase": "core12", "stage_index": stage_index}
            else:
                row = evaluate_coordinate(
                    evaluator,
                    "core12",
                    stage_index,
                    instance,
                    REPO_ROOT / item["path"],
                    30.0,
                    candidate,
                )
            append_csv(results_path, row)
            rows.append(row)
            completed.add(key)
    return rows


def summarize(
    output_dir: Path,
    manifest: dict[str, Any],
    catalog: list[dict[str, Any]],
    ladder_rows: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    quality_archive: list[dict[str, Any]],
    scalability_archive: list[dict[str, Any]],
    core12_rows: list[dict[str, Any]],
) -> None:
    stage_summary = []
    previous_count = len(catalog)
    for stage in LADDER:
        rows = stage_rows(ladder_rows, "ladder", stage["instance"])
        feasible_rows = [row for row in rows if feasible_value(row["feasible"])]
        stage_summary.append(
            {
                "instance": stage["instance"],
                "timeout_s": stage["timeout_s"],
                "input_count": previous_count,
                "feasible_count": len(feasible_rows),
                "timeout_count": sum(row.get("error_type") == "HeldOutTimeout" for row in rows),
                "median_wall_time_s": statistics.median(float(row["wall_time_s"]) for row in rows) if rows else None,
            }
        )
        previous_count = len(feasible_rows)

    per_code = []
    for candidate in scalability_archive:
        rows = [row for row in core12_rows if row["code_hash"] == candidate["code_hash"]]
        gaps = [float(row["relative_gap_pct"]) for row in rows if feasible_value(row["feasible"]) and row["relative_gap_pct"] not in (None, "")]
        per_code.append(
            {
                "code_hash": candidate["code_hash"],
                "original_index": candidate["original_index"],
                "objective": candidate["objective"],
                "feasible_count": sum(feasible_value(row["feasible"]) for row in rows),
                "instance_count": len(rows),
                "median_relative_gap_pct": statistics.median(gaps) if gaps else None,
            }
        )

    summary = {
        "schema_version": "tsp-history-scalability-audit-summary/v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "repo_commit": manifest["repo_commit"],
        "history_rows": manifest["history_row_count"],
        "unique_codes": len(catalog),
        "duplicate_rows_removed": manifest["history_row_count"] - len(catalog),
        "ladder": stage_summary,
        "full_ladder_survivors": len(survivors),
        "quality_archive": [item["code_hash"] for item in quality_archive],
        "scalability_archive": [item["code_hash"] for item in scalability_archive],
        "core12": per_code,
    }
    write_json(output_dir / "audit_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def run(output_dir: Path) -> None:
    manifest, catalog, registry = load_frozen_inputs(output_dir)
    evaluator = import_evaluator()
    ladder_rows, survivors = run_ladder(output_dir, catalog, registry, evaluator)
    quality_archive, scalability_archive = freeze_archives(output_dir, catalog, ladder_rows, survivors)
    core12_rows = run_core12(output_dir, scalability_archive, registry, ladder_rows, evaluator)
    summarize(
        output_dir,
        manifest,
        catalog,
        ladder_rows,
        survivors,
        quality_archive,
        scalability_archive,
        core12_rows,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.command == "prepare":
        prepare(output_dir)
    else:
        run(output_dir)


if __name__ == "__main__":
    main()
