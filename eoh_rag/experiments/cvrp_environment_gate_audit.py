"""离线审计 CVRP 总平均确认门是否会掩盖单一环境退化。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from eoh_rag.experiments.cvrp_fresh_diagnostic import compile_heuristic
from official_eoh.examples.cvrp_construct.prob_broad import CVRPCONSTBroad


def code_sha256(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest().upper()


def _collect_codes(value: Any, source: Path, candidates: dict[str, dict[str, Any]]) -> None:
    """递归提取候选代码；只保留 CVRP 统一接口，避免混入其他问题。"""
    if isinstance(value, dict):
        for key in ("code", "best_code"):
            code = value.get(key)
            if isinstance(code, str) and "def select_next_node" in code:
                digest = code_sha256(code)
                candidates.setdefault(
                    digest,
                    {"code": code, "source_path": str(source)},
                )
        for child in value.values():
            _collect_codes(child, source, candidates)
    elif isinstance(value, list):
        for child in value:
            _collect_codes(child, source, candidates)


def extract_candidates(
    repo_root: Path,
    roots: list[str],
    max_file_bytes: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """按冻结目录清点 JSON 资产；解析失败显式计数，不静默当作空文件。"""
    candidates: dict[str, dict[str, Any]] = {}
    scanned_files = 0
    parse_errors = 0
    for relative_root in roots:
        root = (repo_root / relative_root).resolve()
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
                continue
            if path.stat().st_size > max_file_bytes:
                continue
            scanned_files += 1
            try:
                text = path.read_text(encoding="utf-8")
                if path.suffix.lower() == ".jsonl":
                    for line in text.splitlines():
                        if line.strip():
                            _collect_codes(json.loads(line), path, candidates)
                else:
                    _collect_codes(json.loads(text), path, candidates)
            except (OSError, UnicodeError, json.JSONDecodeError):
                parse_errors += 1
    return candidates, {"scanned_files": scanned_files, "parse_errors": parse_errors}


def load_reference(path: Path, candidate_id: str) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload:
        if item.get("candidate_id") == candidate_id:
            code = item["code"]
            expected = item.get("code_sha256")
            actual = code_sha256(code)
            if expected and expected != actual:
                raise ValueError(f"reference hash mismatch: {candidate_id}")
            return {"candidate_id": candidate_id, "code": code, "code_sha256": actual}
    raise ValueError(f"reference candidate not found: {candidate_id}")


def evaluate_code(code: str, n_train: int, n_confirm: int) -> dict[str, Any]:
    heuristic = compile_heuristic(code)
    problem = CVRPCONSTBroad(
        n_train=n_train,
        confirmation_feedback=True,
        n_confirm=n_confirm,
        training_profile="multi_env_50_100_200",
    )
    search = problem._evaluate_instances(heuristic, problem.instance_data)
    confirm = problem._evaluate_instances(heuristic, problem.confirmation_data)
    if search is None or confirm is None:
        raise ValueError("candidate produced an infeasible route")
    return {
        "search_objective": search[0],
        "search_environment_objectives": search[1],
        "confirm_objective": confirm[0],
        "confirm_environment_objectives": confirm[1],
    }


def evaluate_in_subprocess(code: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """每个历史候选放入独立进程，超时候可终止，避免坏代码卡住整次审计。"""
    payload = {
        "code": code,
        "n_train": int(manifest["n_train"]),
        "n_confirm": int(manifest["n_confirm"]),
    }
    command = [sys.executable, "-m", "eoh_rag.experiments.cvrp_environment_gate_audit", "--worker"]
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=float(manifest["candidate_timeout_seconds"]),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error_type": "timeout"}
    if completed.returncode != 0:
        error_type = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "worker_error"
        return {"ok": False, "error_type": error_type[:160]}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "invalid_worker_output"}
    return {"ok": True, **result}


def classify_candidate(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    regression_limit_pct: float,
) -> dict[str, Any]:
    search_delta = 100.0 * (
        reference["search_objective"] - candidate["search_objective"]
    ) / reference["search_objective"]
    confirm_delta = 100.0 * (
        reference["confirm_objective"] - candidate["confirm_objective"]
    ) / reference["confirm_objective"]
    environment_deltas = {
        name: 100.0 * (reference_cost - candidate["confirm_environment_objectives"][name])
        / reference_cost
        for name, reference_cost in reference["confirm_environment_objectives"].items()
    }
    current_gate_accepted = search_delta > 0.0 and confirm_delta >= 0.0
    regressed_environments = sorted(
        name for name, delta in environment_deltas.items() if delta < -regression_limit_pct
    )
    return {
        "search_improvement_pct": search_delta,
        "confirm_improvement_pct": confirm_delta,
        "confirm_environment_improvement_pct": environment_deltas,
        "improved_environment_count": sum(delta > 0.0 for delta in environment_deltas.values()),
        "worst_environment_improvement_pct": min(environment_deltas.values()),
        "current_gate_accepted": current_gate_accepted,
        "environment_conflict": current_gate_accepted and bool(regressed_environments),
        "regressed_environments": regressed_environments,
    }


def run_audit(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    candidates, inventory = extract_candidates(
        repo_root,
        list(manifest["candidate_roots"]),
        int(manifest["max_file_bytes"]),
    )
    reference_path = (repo_root / manifest["reference_file"]).resolve()
    reference = load_reference(reference_path, manifest["reference_candidate_id"])
    candidates.pop(reference["code_sha256"], None)
    selected_hashes = sorted(candidates)[: int(manifest["sample_size"])]

    reference_result = evaluate_code(
        reference["code"], int(manifest["n_train"]), int(manifest["n_confirm"])
    )
    rows: list[dict[str, Any]] = []
    valid_count = 0
    for digest in selected_hashes:
        item = candidates[digest]
        result = evaluate_in_subprocess(item["code"], manifest)
        row: dict[str, Any] = {
            "code_sha256": digest,
            "source_path": str(Path(item["source_path"]).resolve().relative_to(repo_root)),
            "valid": bool(result["ok"]),
        }
        if result["ok"]:
            valid_count += 1
            row.update(
                classify_candidate(
                    reference_result,
                    result,
                    float(manifest["environment_regression_limit_pct"]),
                )
            )
        else:
            row["error_type"] = result["error_type"]
        rows.append(row)

    accepted = sum(row.get("current_gate_accepted", False) for row in rows)
    conflicts = sum(row.get("environment_conflict", False) for row in rows)
    conflict_rate = conflicts / accepted if accepted else None
    trigger = float(manifest["conflict_rate_trigger"])
    decision = (
        "insufficient_accepted_candidates"
        if accepted == 0
        else "implement_environment_robust_gate"
        if conflict_rate is not None and conflict_rate >= trigger
        else "retain_current_gate_and_monitor"
    )
    return {
        "suite": manifest["suite"],
        "held_out_used": False,
        "inventory": {
            **inventory,
            "unique_candidate_codes": len(candidates) + 1,
            "deterministic_sample_size": len(selected_hashes),
            "valid_sample_size": valid_count,
        },
        "reference": {
            "candidate_id": reference["candidate_id"],
            "code_sha256": reference["code_sha256"],
            **reference_result,
        },
        "gate_audit": {
            "current_gate_accepted": accepted,
            "environment_conflicts": conflicts,
            "conflict_rate": conflict_rate,
            "conflict_rate_trigger": trigger,
            "environment_regression_limit_pct": float(
                manifest["environment_regression_limit_pct"]
            ),
            "decision": decision,
        },
        "candidates": rows,
    }


def render_markdown(result: dict[str, Any]) -> str:
    inventory = result["inventory"]
    audit = result["gate_audit"]
    rate = "无可计算值" if audit["conflict_rate"] is None else f"{audit['conflict_rate']:.1%}"
    return "\n".join(
        [
            "# CVRP 环境门漏网审计",
            "",
            f"结论：`{audit['decision']}`。",
            "",
            f"- 去重候选：{inventory['unique_candidate_codes']}",
            f"- 固定抽样：{inventory['deterministic_sample_size']}，有效：{inventory['valid_sample_size']}",
            f"- 当前门接纳：{audit['current_gate_accepted']}",
            f"- 环境冲突：{audit['environment_conflicts']}，冲突率：{rate}",
            "- held-out 未参与清点、评分或决策。",
            "",
        ]
    )


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def worker_main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        result = evaluate_code(payload["code"], int(payload["n_train"]), int(payload["n_confirm"]))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # 子进程只回传错误类型，避免历史代码或大日志泄漏。
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
    json_path = output_dir / "cvrp_environment_gate_audit.json"
    markdown_path = output_dir / "cvrp_environment_gate_audit.md"
    if not args.force and (json_path.exists() or markdown_path.exists()):
        raise FileExistsError(f"audit output already exists: {output_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repo_root = Path(__file__).resolve().parents[2]
    result = run_audit(manifest, repo_root)
    result["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    write_atomic(json_path, json.dumps(result, ensure_ascii=False, indent=2))
    write_atomic(markdown_path, render_markdown(result))
    print(json.dumps({"output": str(json_path), **result["gate_audit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
