"""在生成后冻结的诊断集上比较 BP 单尺度与多尺度进化输出。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_bp_generalization import _paired_summary, evaluate_pair  # noqa: E402


def _sha256_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest().upper()


def _load_run_code(report_root: Path, arm: str, seed: int) -> dict[str, Any]:
    summary_path = report_root / arm / str(seed) / "official_eoh_run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_summary = summary.get("run_summary") or {}
    if summary.get("failure_reason") or not run_summary.get("ok"):
        raise ValueError(f"source run is incomplete: {arm}/{seed}")
    expected_profile = arm
    if summary.get("bp_training_profile") != expected_profile:
        raise ValueError(f"training profile mismatch: {arm}/{seed}")
    code = run_summary.get("best_code")
    if not isinstance(code, str) or not code:
        raise ValueError(f"source run has no final code: {arm}/{seed}")
    return {
        "code": code,
        "code_sha256": _sha256_code(code),
        "source_summary": str(summary_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "source_objective": run_summary.get("best_objective"),
        "runtime_seconds": summary.get("runtime_seconds"),
    }


def _build_tasks(
    manifest: dict[str, Any], baseline_code: str, agent_code: str
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    generator = manifest["generator"]
    for scale_index, item_count in enumerate(generator["item_counts"]):
        for instance_index in range(int(generator["instances_per_scale"])):
            tasks.append(
                {
                    "capacity": 100,
                    "generator": generator,
                    "item_count": int(item_count),
                    "instance_index": instance_index,
                    "seed": int(generator["seed_start"])
                    + scale_index * int(generator["seed_stride"])
                    + instance_index,
                    "candidates": [
                        {"candidate_id": "single_5k", "code": baseline_code},
                        {"candidate_id": "balanced_1k_5k_10k", "code": agent_code},
                    ],
                }
            )
    return tasks


def _evaluate_tasks(tasks: list[dict[str, Any]], workers: int) -> tuple[list[dict], list[dict]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(evaluate_pair, task): task for task in tasks}
        for future in concurrent.futures.as_completed(future_map):
            task = future_map[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 失败坐标必须进入诊断证据
                failures.append(
                    {
                        "item_count": task["item_count"],
                        "instance_index": task["instance_index"],
                        "seed": task["seed"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
    rows.sort(key=lambda row: (row["item_count"], row["instance_index"]))
    return rows, failures


def _summarize_pair(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    by_scale = {
        str(item_count): _paired_summary(
            [row for row in rows if row["item_count"] == item_count],
            "single_5k",
            "balanced_1k_5k_10k",
        )
        for item_count in manifest["generator"]["item_counts"]
    }
    return {
        "overall": _paired_summary(rows, "single_5k", "balanced_1k_5k_10k"),
        "by_scale": by_scale,
    }


def gate_checks(pair_summaries: list[dict[str, Any]], failures: list[dict], manifest: dict) -> dict:
    gate = manifest["proxy_gate"]
    balanced_better = sum(
        pair["overall"]["gap_reduction_pct_points"]["mean"] > 0 for pair in pair_summaries
    )
    one_k_not_worse = sum(
        pair["by_scale"]["1000"]["gap_reduction_pct_points"]["mean"] >= 0
        for pair in pair_summaries
    )
    valid_pairs = sum(pair["overall"]["pairs"] for pair in pair_summaries)
    return {
        "valid_instance_pairs": valid_pairs >= int(gate["valid_instance_pairs_min"]),
        "no_failed_instances": not failures,
        "balanced_beats_single_seed_pairs": balanced_better
        >= int(gate["balanced_beats_single_seed_pairs_min"]),
        "balanced_1k_mean_gap_not_worse_seed_pairs": one_k_not_worse
        >= int(gate["balanced_1k_mean_gap_not_worse_seed_pairs_min"]),
    }


def run(manifest_path: Path, output_path: Path, workers: int) -> int:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    report_root = (REPO_ROOT / manifest["source_report_root"]).resolve()
    started = time.time()
    source_runs: list[dict[str, Any]] = []
    pair_summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for seed in manifest["pair_seeds"]:
        baseline = _load_run_code(report_root, manifest["baseline_arm"], seed)
        agent = _load_run_code(report_root, manifest["agent_arm"], seed)
        source_runs.append({"seed": seed, "baseline": baseline, "agent": agent})
        rows, pair_failures = _evaluate_tasks(
            _build_tasks(manifest, baseline["code"], agent["code"]), workers
        )
        for row in rows:
            row["evolution_seed"] = seed
        for failure in pair_failures:
            failure["evolution_seed"] = seed
        all_rows.extend(rows)
        failures.extend(pair_failures)
        pair_summaries.append({"evolution_seed": seed, **_summarize_pair(rows, manifest)})
        print(f"evolution_seed={seed} pairs={len(rows)} failures={len(pair_failures)}", flush=True)

    checks = gate_checks(pair_summaries, failures, manifest)
    payload = {
        "schema_version": manifest["schema_version"],
        "suite": manifest["suite"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest().upper(),
        "freeze_timing": manifest["freeze_timing"],
        "runtime_seconds": round(time.time() - started, 3),
        "source_runs": [
            {
                "seed": row["seed"],
                "baseline": {key: value for key, value in row["baseline"].items() if key != "code"},
                "agent": {key: value for key, value in row["agent"].items() if key != "code"},
            }
            for row in source_runs
        ],
        "pair_summaries": pair_summaries,
        "failures": failures,
        "gate_checks": checks,
        "gate_passed": all(checks.values()),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pairs_path = output_path.with_name("bp_scale_proxy_diagnostic_pairs.jsonl")
    pairs_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_rows), encoding="utf-8"
    )
    print(json.dumps({"output": str(output_path), "gate_passed": payload["gate_passed"]}))
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    raise SystemExit(run(Path(args.manifest).resolve(), Path(args.output).resolve(), args.workers))


if __name__ == "__main__":
    main()
