"""在冻结的 CVRP Core 上生成一次性最终泛化报告。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import median
from typing import Any

from eoh_rag.experiments.cvrp_fresh_diagnostic import compile_heuristic
from official_eoh.examples.core_benchmarks import evaluate_cvrp, load_cvrp


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_candidates(path: Path, candidate_ids: list[str]) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected: dict[str, dict[str, str]] = {}
    for item in payload:
        candidate_id = item.get("candidate_id")
        if candidate_id not in candidate_ids:
            continue
        code = item["code"]
        actual_hash = hashlib.sha256(code.encode("utf-8")).hexdigest().upper()
        if item.get("code_sha256") != actual_hash:
            raise ValueError(f"candidate hash mismatch: {candidate_id}")
        selected[candidate_id] = {"code": code, "code_sha256": actual_hash}
    missing = sorted(set(candidate_ids) - set(selected))
    if missing:
        raise ValueError(f"missing candidates: {missing}")
    return selected


def load_core_instances(registry_path: Path, repo_root: Path) -> list[dict[str, str]]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for item in registry["instances"]:
        if item.get("problem") != "cvrp_construct":
            continue
        instance_path = (repo_root / item["path"]).resolve()
        if file_sha256(instance_path) != str(item["sha256"]).upper():
            raise ValueError(f"instance hash mismatch: {item['instance']}")
        rows.append({"instance": item["instance"], "path": str(instance_path)})
    return rows


def evaluate_coordinate(code: str, instance_path: str) -> dict[str, Any]:
    heuristic = compile_heuristic(code)
    return evaluate_cvrp(heuristic, load_cvrp(instance_path))


def run_coordinate(
    candidate_id: str,
    candidate: dict[str, str],
    instance: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    """坐标放入独立进程；超时与算法异常均写入正式结果，不能静默删失。"""
    payload = {"code": candidate["code"], "instance_path": instance["path"]}
    command = [sys.executable, "-m", "eoh_rag.experiments.cvrp_core_final_report", "--worker"]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "candidate_id": candidate_id,
            "code_sha256": candidate["code_sha256"],
            "instance": instance["instance"],
            "ok": False,
            "error_type": "timeout",
            "runtime_seconds": timeout_seconds,
        }
    runtime = time.perf_counter() - started
    if completed.returncode != 0:
        error_type = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "worker_error"
        return {
            "candidate_id": candidate_id,
            "code_sha256": candidate["code_sha256"],
            "instance": instance["instance"],
            "ok": False,
            "error_type": error_type[:160],
            "runtime_seconds": runtime,
        }
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "candidate_id": candidate_id,
            "code_sha256": candidate["code_sha256"],
            "instance": instance["instance"],
            "ok": False,
            "error_type": "invalid_worker_output",
            "runtime_seconds": runtime,
        }
    return {
        "candidate_id": candidate_id,
        "code_sha256": candidate["code_sha256"],
        "instance": instance["instance"],
        "ok": True,
        "runtime_seconds": runtime,
        **report,
    }


def summarize_pairs(rows: list[dict[str, Any]], baseline_id: str, candidate_id: str) -> dict[str, Any]:
    by_coordinate = {(row["candidate_id"], row["instance"]): row for row in rows}
    improvements: list[float] = []
    pairs: list[dict[str, Any]] = []
    for instance in sorted({row["instance"] for row in rows}):
        baseline = by_coordinate.get((baseline_id, instance))
        candidate = by_coordinate.get((candidate_id, instance))
        if not baseline or not candidate or not baseline["ok"] or not candidate["ok"]:
            continue
        improvement = 100.0 * (baseline["route_cost"] - candidate["route_cost"]) / baseline["route_cost"]
        improvements.append(improvement)
        pairs.append({"instance": instance, "relative_improvement_pct": improvement})
    return {
        "paired_instances": len(improvements),
        "wins": sum(value > 0.0 for value in improvements),
        "losses": sum(value < 0.0 for value in improvements),
        "ties": sum(value == 0.0 for value in improvements),
        "median_relative_improvement_pct": median(improvements) if improvements else None,
        "pairs": pairs,
    }


def run_report(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    registry_path = (repo_root / manifest["registry_file"]).resolve()
    candidate_path = (repo_root / manifest["candidate_file"]).resolve()
    if file_sha256(registry_path) != manifest["registry_sha256"]:
        raise ValueError("registry hash mismatch")
    if file_sha256(candidate_path) != manifest["candidate_file_sha256"]:
        raise ValueError("candidate file hash mismatch")

    candidate_ids = list(manifest["candidate_ids"])
    candidates = load_candidates(candidate_path, candidate_ids)
    instances = load_core_instances(registry_path, repo_root)
    coordinates = [
        (candidate_id, candidates[candidate_id], instance)
        for instance in instances
        for candidate_id in candidate_ids
    ]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=int(manifest["max_concurrent_coordinates"])) as executor:
        futures = [
            executor.submit(
                run_coordinate,
                candidate_id,
                candidate,
                instance,
                float(manifest["coordinate_timeout_seconds"]),
            )
            for candidate_id, candidate, instance in coordinates
        ]
        for future in as_completed(futures):
            rows.append(future.result())
    instance_order = {item["instance"]: index for index, item in enumerate(instances)}
    candidate_order = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
    rows.sort(key=lambda row: (instance_order[row["instance"]], candidate_order[row["candidate_id"]]))

    status = {
        candidate_id: {
            "completed": sum(row["ok"] for row in rows if row["candidate_id"] == candidate_id),
            "failed": sum(not row["ok"] for row in rows if row["candidate_id"] == candidate_id),
            "timeouts": sum(
                row.get("error_type") == "timeout"
                for row in rows
                if row["candidate_id"] == candidate_id
            ),
        }
        for candidate_id in candidate_ids
    }
    return {
        "suite": manifest["suite"],
        "held_out_used": True,
        "held_out_controls_selection": False,
        "core_instance_count": len(instances),
        "coordinate_count": len(rows),
        "candidate_status": status,
        "paired_comparison": summarize_pairs(rows, candidate_ids[0], candidate_ids[1]),
        "coordinates": rows,
    }


def render_markdown(result: dict[str, Any]) -> str:
    comparison = result["paired_comparison"]
    lines = [
        "# CVRP 完整 Core 最终泛化报告",
        "",
        f"完成 {result['coordinate_count']} 个冻结坐标；held-out 不参与算法选择。",
        "",
        "| 算法 | 完成 | 失败 | 超时 |",
        "|---|---:|---:|---:|",
    ]
    for candidate_id, status in result["candidate_status"].items():
        lines.append(
            f"| {candidate_id} | {status['completed']} | {status['failed']} | {status['timeouts']} |"
        )
    median_text = (
        "无可配对实例"
        if comparison["median_relative_improvement_pct"] is None
        else f"{comparison['median_relative_improvement_pct']:.4f}%"
    )
    lines.extend(
        [
            "",
            f"n2 相对 seed：{comparison['wins']} 胜 / {comparison['losses']} 负 / "
            f"{comparison['ties']} 平；配对中位改善 {median_text}。",
            "",
        ]
    )
    return "\n".join(lines)


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def worker_main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        report = evaluate_coordinate(payload["code"], payload["instance_path"])
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:  # 只回传错误类型，避免候选代码或大日志进入正式结果。
        print(type(exc).__name__, file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest")
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker_main())
    if not args.manifest or not args.output_dir:
        parser.error("--manifest and --output-dir are required")

    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    json_path = output_dir / "cvrp_core_final_report.json"
    markdown_path = output_dir / "cvrp_core_final_report.md"
    if not args.force and (json_path.exists() or markdown_path.exists()):
        raise FileExistsError(f"final report already exists: {output_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]
    result = run_report(manifest, repo_root)
    result["manifest_sha256"] = file_sha256(manifest_path)
    write_atomic(json_path, json.dumps(result, ensure_ascii=False, indent=2))
    write_atomic(markdown_path, render_markdown(result))
    print(json.dumps({"output": str(json_path), **result["candidate_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
