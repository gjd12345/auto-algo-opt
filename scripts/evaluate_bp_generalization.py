"""在冻结随机实例上配对评估 BP 算法的跨规模泛化。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_candidate_code(asset: Any, code_sha256: str) -> str:
    """按已冻结代码哈希取算法，避免列表顺序变化后选错历史精英。"""
    rows = asset if isinstance(asset, list) else [asset]
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str):
            continue
        code = row["code"]
        if _sha256_bytes(code.encode()) == code_sha256.upper():
            return code
    raise ValueError(f"candidate code hash not found: {code_sha256}")


def load_candidates(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """读取候选资产并同时校验资产哈希与代码哈希。"""
    candidates: list[dict[str, str]] = []
    for item in manifest["candidates"]:
        asset_path = (REPO_ROOT / item["asset_path"]).resolve()
        if not asset_path.is_relative_to(REPO_ROOT):
            raise ValueError(f"candidate asset escapes repository: {item['asset_path']}")
        asset_bytes = asset_path.read_bytes()
        actual_asset_hash = _sha256_bytes(asset_bytes)
        if actual_asset_hash != item["asset_sha256"].upper():
            raise ValueError(f"candidate asset hash mismatch: {item['candidate_id']}")
        code = _resolve_candidate_code(json.loads(asset_bytes), item["code_sha256"])
        candidates.append(
            {
                "candidate_id": item["candidate_id"],
                "actor": item["actor"],
                "asset_path": item["asset_path"],
                "asset_sha256": actual_asset_hash,
                "code_sha256": _sha256_bytes(code.encode()),
                "code": code,
            }
        )
    if len(candidates) != 2:
        raise ValueError("paired generalization confirmation requires exactly two candidates")
    return candidates


def _generate_items(generator: dict[str, Any], item_count: int, seed: int) -> np.ndarray:
    if generator["distribution"] != "weibull":
        raise ValueError(f"unsupported distribution: {generator['distribution']}")
    rng = np.random.default_rng(seed)
    items = rng.weibull(float(generator["shape"]), item_count) * float(generator["scale"])
    return np.clip(
        np.round(items).astype(int),
        int(generator["clip_min"]),
        int(generator["clip_max"]),
    )


def _compile_score(code: str):
    namespace: dict[str, Any] = {"np": np}
    exec(code, namespace)
    score = namespace.get("score")
    if not callable(score):
        raise ValueError("candidate does not define callable score")
    return score


def _used_bin_count(items: np.ndarray, capacity: int, code: str) -> int:
    """严格复用官方 BP 语义：所有空箱都保留，np.argmax 取第一个并列项。"""
    score = _compile_score(code)
    bins = np.full(len(items), capacity, dtype=int)
    for item in items:
        valid = np.nonzero((bins - item) >= 0)[0]
        priorities = np.asarray(score(int(item), bins[valid]), dtype=float)
        if priorities.shape != (len(valid),) or not np.all(np.isfinite(priorities)):
            raise ValueError("candidate returned invalid priority vector")
        best = valid[int(np.argmax(priorities))]
        bins[best] -= int(item)
    return int(np.count_nonzero(bins != capacity))


def evaluate_pair(task: dict[str, Any]) -> dict[str, Any]:
    """单个 worker 内同时评估一对候选，保证二者看到完全相同的实例。"""
    items = _generate_items(task["generator"], task["item_count"], task["seed"])
    capacity = int(task["capacity"])
    lower_bound = int(math.ceil(float(items.sum()) / capacity))
    results: dict[str, dict[str, float | int]] = {}
    for candidate in task["candidates"]:
        used = _used_bin_count(items, capacity, candidate["code"])
        results[candidate["candidate_id"]] = {
            "used_bins": used,
            "gap_pct": (used - lower_bound) / lower_bound * 100.0,
        }
    return {
        "item_count": task["item_count"],
        "instance_index": task["instance_index"],
        "seed": task["seed"],
        "lower_bound": lower_bound,
        "results": results,
    }


def _distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "std": float(array.std()),
        "p90": float(np.quantile(array, 0.9)),
        "max": float(array.max()),
    }


def _sign_test_p_value(wins: int, losses: int) -> float:
    """精确双侧符号检验；平局不进入有效配对数。"""
    total = wins + losses
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, index) for index in range(min(wins, losses) + 1)) / (2**total)
    return min(1.0, 2.0 * tail)


def _paired_summary(rows: list[dict[str, Any]], baseline_id: str, agent_id: str) -> dict[str, Any]:
    reductions = [
        row["results"][baseline_id]["gap_pct"] - row["results"][agent_id]["gap_pct"]
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
    rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    runtime_seconds: float,
) -> dict[str, Any]:
    baseline_id = manifest["comparison"]["baseline_candidate_id"]
    agent_id = manifest["comparison"]["agent_candidate_id"]
    by_scale: dict[str, Any] = {}
    for item_count in manifest["generator"]["item_counts"]:
        scale_rows = [row for row in rows if row["item_count"] == item_count]
        by_scale[str(item_count)] = _paired_summary(scale_rows, baseline_id, agent_id)
    overall = _paired_summary(rows, baseline_id, agent_id)
    candidate_metrics = {
        candidate["candidate_id"]: _distribution(
            [row["results"][candidate["candidate_id"]]["gap_pct"] for row in rows]
        )
        for candidate in candidates
    }
    gate = manifest["confirmation_gate"]
    positive_scales = sum(
        value["gap_reduction_pct_points"]["mean"] > 0 for value in by_scale.values()
    )
    checks = {
        "valid_pairs": len(rows) >= int(gate["valid_pairs_min"]),
        "no_failed_pairs": not failures,
        "overall_mean_gap_reduction_positive": overall["gap_reduction_pct_points"]["mean"] > 0,
        "overall_wins_exceed_losses": overall["wins"] > overall["losses"],
        "sign_test": overall["sign_test_p_value"] < float(gate["sign_test_p_value_max"]),
        "positive_scale_count": positive_scales >= int(gate["positive_scale_count_min"]),
    }
    return {
        "schema_version": "bp_generalization_confirmation/v1",
        "suite": manifest["suite"],
        "actor": "evaluation_pipeline",
        "research_candidate_actor": next(
            candidate["actor"] for candidate in candidates if candidate["candidate_id"] == agent_id
        ),
        "manifest_sha256": manifest_hash,
        "repository_commit": _git_commit(),
        "runtime_seconds": runtime_seconds,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "generator": manifest["generator"],
        "candidates": [
            {key: candidate[key] for key in ("candidate_id", "actor", "asset_path", "asset_sha256", "code_sha256")}
            for candidate in candidates
        ],
        "valid_pairs": len(rows),
        "failed_pairs": failures,
        "candidate_metrics": candidate_metrics,
        "paired_overall": overall,
        "paired_by_scale": by_scale,
        "gate_checks": checks,
        "gate_passed": all(checks.values()),
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def run(manifest_path: Path, output_dir: Path, workers: int, force: bool = False) -> int:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_hash = _sha256_bytes(manifest_bytes)
    candidates = load_candidates(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "bp_generalization_summary.json"
    pairs_path = output_dir / "bp_generalization_pairs.jsonl"
    if summary_path.exists() and not force:
        raise FileExistsError(f"summary already exists: {summary_path}")

    tasks: list[dict[str, Any]] = []
    generator = manifest["generator"]
    for scale_index, item_count in enumerate(generator["item_counts"]):
        for instance_index in range(int(generator["instances_per_scale"])):
            tasks.append(
                {
                    "capacity": manifest["capacity"],
                    "generator": generator,
                    "item_count": int(item_count),
                    "instance_index": instance_index,
                    "seed": int(generator["seed_start"])
                    + scale_index * int(generator["seed_stride"])
                    + instance_index,
                    "candidates": [
                        {"candidate_id": candidate["candidate_id"], "code": candidate["code"]}
                        for candidate in candidates
                    ],
                }
            )

    started = time.time()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(evaluate_pair, task): task for task in tasks}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), start=1):
            task = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 每个失败坐标必须进入正式证据
                failures.append(
                    {
                        "item_count": task["item_count"],
                        "instance_index": task["instance_index"],
                        "seed": task["seed"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if completed % 25 == 0 or completed == len(tasks):
                print(f"completed={completed}/{len(tasks)} failures={len(failures)}", flush=True)

    rows.sort(key=lambda row: (row["item_count"], row["instance_index"]))
    pairs_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    summary = build_summary(
        manifest,
        manifest_hash,
        candidates,
        rows,
        failures,
        round(time.time() - started, 3),
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "gate_passed": summary["gate_passed"]}))
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.manifest).resolve(), Path(args.output_dir).resolve(), args.workers, args.force))


if __name__ == "__main__":
    main()
