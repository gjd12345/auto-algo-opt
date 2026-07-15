"""在冻结 HiFo 数据上比较 BP 候选与继承精英的分布外泛化。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import pickle
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# 直接以 `python scripts/...py` 启动时，默认模块路径只有 scripts 目录；显式加入仓库根目录，
# 保证本地、CI 和其他设备都能复用同一评估函数。
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_bp_generalization import (
    _distribution,
    _git_commit,
    _sign_test_p_value,
    _used_bin_count,
    load_candidates,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _extract_instances(raw: Any) -> list[np.ndarray]:
    """按官方 BP held-out 合同展开实例，不猜测额外字段。"""
    instances: list[np.ndarray] = []
    if not isinstance(raw, dict):
        return instances
    for value in raw.values():
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, dict) and "items" in nested:
                    instances.append(np.asarray(nested["items"], dtype=int))
        elif isinstance(value, list) and value and isinstance(
            value[0], (list, tuple, np.ndarray)
        ):
            instances.extend(np.asarray(items, dtype=int) for items in value)
    return instances


def load_datasets(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """先核对固定上游哈希，再读取可信 pickle，防止误评其他本地文件。"""
    datasets: list[dict[str, Any]] = []
    for item in manifest["datasets"]:
        path = (REPO_ROOT / item["path"]).resolve()
        if not path.is_relative_to(REPO_ROOT):
            raise ValueError(f"dataset escapes repository: {item['path']}")
        actual_hash = _sha256(path)
        if actual_hash != item["sha256"].upper():
            raise ValueError(f"dataset hash mismatch: {item['dataset_id']}")
        # 文件来自固定 HiFo commit 且已核对哈希；哈希通过前禁止反序列化。
        instances = _extract_instances(pickle.loads(path.read_bytes()))
        if len(instances) != int(item["expected_instances"]):
            raise ValueError(f"unexpected instance count: {item['dataset_id']}")
        datasets.append({**item, "sha256": actual_hash, "instances": instances})
    return datasets


def evaluate_pair(task: dict[str, Any]) -> dict[str, Any]:
    """同一 worker 内评价两份代码，保证实例和下界完全配对。"""
    items = np.asarray(task["items"], dtype=int)
    capacity = int(task["capacity"])
    lower_bound = int(np.ceil(float(items.sum()) / capacity))
    results: dict[str, dict[str, float | int]] = {}
    for candidate in task["candidates"]:
        used_bins = _used_bin_count(items, capacity, candidate["code"])
        results[candidate["candidate_id"]] = {
            "used_bins": used_bins,
            "gap_pct": (used_bins - lower_bound) / lower_bound * 100.0,
        }
    return {
        "dataset_id": task["dataset_id"],
        "item_count": int(task["item_count"]),
        "instance_index": int(task["instance_index"]),
        "lower_bound": lower_bound,
        "results": results,
    }


def _paired_summary(
    rows: list[dict[str, Any]], baseline_id: str, agent_id: str
) -> dict[str, Any]:
    reductions = [
        row["results"][baseline_id]["gap_pct"]
        - row["results"][agent_id]["gap_pct"]
        for row in rows
    ]
    wins = sum(value > 0 for value in reductions)
    ties = sum(value == 0 for value in reductions)
    losses = sum(value < 0 for value in reductions)
    return {
        "pairs": len(rows),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "sign_test_p_value": _sign_test_p_value(wins, losses),
        "gap_reduction_pct_points": _distribution(reductions),
    }


def build_summary(
    manifest: dict[str, Any],
    manifest_hash: str,
    candidates: list[dict[str, str]],
    datasets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    runtime_seconds: float,
) -> dict[str, Any]:
    baseline_id = manifest["comparison"]["baseline_candidate_id"]
    agent_id = manifest["comparison"]["agent_candidate_id"]
    by_dataset = {
        dataset["dataset_id"]: _paired_summary(
            [row for row in rows if row["dataset_id"] == dataset["dataset_id"]],
            baseline_id,
            agent_id,
        )
        for dataset in datasets
    }
    overall = _paired_summary(rows, baseline_id, agent_id)
    gate = manifest["scope_extension_gate"]
    checks = {
        "valid_pairs": len(rows) >= int(gate["valid_pairs_min"]),
        "no_failed_pairs": not failures,
        "overall_mean_gap_reduction_positive": overall["gap_reduction_pct_points"]["mean"]
        > 0,
        "sign_test": overall["sign_test_p_value"]
        < float(gate["sign_test_p_value_max"]),
        "positive_dataset_count": sum(
            item["gap_reduction_pct_points"]["mean"] > 0 for item in by_dataset.values()
        )
        >= int(gate["positive_dataset_count_min"]),
    }
    return {
        "schema_version": manifest["schema_version"],
        "suite": manifest["suite"],
        "actor": "evaluation_pipeline",
        "research_candidate_actor": next(
            item["actor"] for item in candidates if item["candidate_id"] == agent_id
        ),
        "manifest_sha256": manifest_hash,
        "repository_commit": _git_commit(),
        "runtime_seconds": runtime_seconds,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "datasets": [
            {
                "dataset_id": item["dataset_id"],
                "path": item["path"],
                "sha256": item["sha256"],
                "instances": len(item["instances"]),
                "item_count": item["item_count"],
            }
            for item in datasets
        ],
        "candidates": [
            {
                key: candidate[key]
                for key in (
                    "candidate_id",
                    "actor",
                    "asset_path",
                    "asset_sha256",
                    "code_sha256",
                )
            }
            for candidate in candidates
        ],
        "valid_pairs": len(rows),
        "failed_pairs": failures,
        "paired_overall": overall,
        "paired_by_dataset": by_dataset,
        "scope_extension_checks": checks,
        "scope_extension_passed": all(checks.values()),
        "interpretation_limit": "HiFo has five fixed instances per scale; report as scope evidence, not a new universal claim.",
    }


def run(manifest_path: Path, output_dir: Path, workers: int) -> int:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    candidates = load_candidates(manifest)
    datasets = load_datasets(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "bp_hifo_summary.json"
    pairs_path = output_dir / "bp_hifo_pairs.jsonl"
    if summary_path.exists():
        raise FileExistsError(f"summary already exists: {summary_path}")

    tasks = [
        {
            "dataset_id": dataset["dataset_id"],
            "item_count": dataset["item_count"],
            "instance_index": index,
            "items": items.tolist(),
            "capacity": manifest["capacity"],
            "candidates": [
                {"candidate_id": item["candidate_id"], "code": item["code"]}
                for item in candidates
            ],
        }
        for dataset in datasets
        for index, items in enumerate(dataset["instances"])
    ]
    started = time.time()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(evaluate_pair, task): task for task in tasks}
        for future in concurrent.futures.as_completed(future_map):
            task = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 失败坐标必须进入正式证据
                failures.append(
                    {
                        "dataset_id": task["dataset_id"],
                        "instance_index": task["instance_index"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
    rows.sort(key=lambda item: (item["item_count"], item["instance_index"]))
    pairs_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows),
        encoding="utf-8",
    )
    summary = build_summary(
        manifest,
        hashlib.sha256(manifest_bytes).hexdigest().upper(),
        candidates,
        datasets,
        rows,
        failures,
        round(time.time() - started, 3),
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"summary": str(summary_path), "scope_extension_passed": summary["scope_extension_passed"]}
        )
    )
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    raise SystemExit(run(Path(args.manifest).resolve(), Path(args.output_dir).resolve(), args.workers))


if __name__ == "__main__":
    main()
