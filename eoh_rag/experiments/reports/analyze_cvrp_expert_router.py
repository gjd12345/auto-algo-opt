"""按冻结 gate 分析 CVRP expert-router proxy，不允许事后修改门槛。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_generated_sample_count(run_dir: Path) -> int:
    """只统计生成样本，不把冻结 seed 当成有效生成结果。"""
    count = 0
    sample_dir = run_dir / "results" / "samples"
    for path in sample_dir.glob("samples_*.json"):
        if path.name == "samples_best.json":
            continue
        try:
            payload = _load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        rows = payload if isinstance(payload, list) else [payload]
        count += sum(
            1
            for row in rows
            if isinstance(row, dict)
            and row.get("objective") is not None
            and isinstance(row.get("code"), str)
            and row["code"].strip()
        )
    return count


def _expected_run_keys(manifest: dict[str, Any]) -> set[str]:
    generations = manifest.get("generations", [0])
    keys: set[str] = set()
    for seed in manifest["seed_list"]:
        for problem in manifest["problems"]:
            for arm in manifest["arms"]:
                if arm.get("problems") and problem not in arm["problems"]:
                    continue
                for generation in generations:
                    base = f"{manifest['suite']}/{problem}/{arm['name']}/{seed}"
                    keys.add(base if len(generations) == 1 else f"{base}/g{generation}")
    return keys


def analyze_proxy(manifest_path: Path, run_root: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    gate = manifest["proxy_gate"]
    index_path = run_root / "run_index.json"
    rows = _load_json(index_path) if index_path.is_file() else []
    rows_by_key = {
        row.get("run_key"): row
        for row in rows
        if isinstance(row, dict) and row.get("run_key")
    }
    expected_keys = _expected_run_keys(manifest)
    missing_keys = sorted(expected_keys - set(rows_by_key))

    completed = 0
    valid_generated_runs = 0
    confirmation_improvements: list[float] = []
    environment_degradations: dict[str, list[float]] = {}
    runs_using_multiple_experts = 0
    selector_invalid_outputs = 0
    infeasible_runs = 0
    run_evidence: list[dict[str, Any]] = []

    for run_key in sorted(expected_keys):
        row = rows_by_key.get(run_key)
        if not row:
            continue
        run_dir = Path(row["output_dir"])
        summary_path = run_dir / "official_eoh_run_summary.json"
        if row.get("status") not in {"ok", "skipped_complete"} or not summary_path.is_file():
            run_evidence.append({"run_key": run_key, "status": row.get("status", "missing_summary")})
            continue
        summary = _load_json(summary_path)
        run_summary = summary.get("run_summary") or {}
        confirmation = run_summary.get("confirmation_report") or {}
        if not run_summary.get("ok") or not confirmation:
            run_evidence.append({"run_key": run_key, "status": "invalid_summary_or_confirmation"})
            continue

        completed += 1
        generated_count = _valid_generated_sample_count(run_dir)
        if generated_count > 0:
            valid_generated_runs += 1
        improvement = float(confirmation["mean_improvement_vs_n2_pct"])
        confirmation_improvements.append(improvement)
        environment_values = confirmation.get("environment_relative_cost_vs_n2") or {}
        for environment, relative_cost in environment_values.items():
            environment_degradations.setdefault(environment, []).append(
                100.0 * float(relative_cost)
            )
        counts = confirmation.get("expert_selection_counts") or {}
        used_experts = sorted(
            expert_id for expert_id, count in counts.items() if int(count) > 0
        )
        if len(used_experts) >= 2:
            runs_using_multiple_experts += 1
        invalid_outputs = int(confirmation.get("selector_invalid_outputs", 0))
        selector_invalid_outputs += invalid_outputs
        feasible = bool((confirmation.get("evaluation_result") or {}).get("feasible"))
        if not feasible:
            infeasible_runs += 1
        run_evidence.append(
            {
                "run_key": run_key,
                "status": "ok",
                "valid_generated_samples": generated_count,
                "confirmation_improvement_vs_n2_pct": improvement,
                "used_experts": used_experts,
                "selector_invalid_outputs": invalid_outputs,
                "feasible": feasible,
            }
        )

    environment_mean_degradation_pct = {
        name: mean(values) for name, values in sorted(environment_degradations.items())
    }
    worst_environment_degradation_pct = (
        max(environment_mean_degradation_pct.values())
        if environment_mean_degradation_pct
        else None
    )
    confirmation_mean_improvement = (
        mean(confirmation_improvements)
        if confirmation_improvements
        else None
    )
    paired_seed_count = len(
        {
            int(rows_by_key[key]["seed"])
            for key in expected_keys & set(rows_by_key)
            if rows_by_key[key].get("status") in {"ok", "skipped_complete"}
        }
    )
    checks = {
        "completed_runs": completed >= int(gate["completed_runs_min"]),
        "valid_generated_runs": valid_generated_runs
        >= int(gate["valid_generated_runs_min"]),
        "paired_seed_count": paired_seed_count >= int(gate["paired_seed_count_min"]),
        "confirmation_mean_improvement": confirmation_mean_improvement is not None
        and confirmation_mean_improvement
        >= float(gate["confirmation_mean_improvement_vs_n2_pct_min"]),
        "confirmation_environment_degradation": worst_environment_degradation_pct
        is not None
        and worst_environment_degradation_pct
        <= float(gate["confirmation_environment_degradation_pct_max"]),
        "multi_expert_usage": runs_using_multiple_experts
        >= int(gate["runs_using_at_least_two_experts_min"]),
        "selector_invalid_outputs": selector_invalid_outputs
        <= int(gate["selector_invalid_outputs_max"]),
        "missing_coordinates": len(missing_keys) <= int(gate["missing_coordinates_max"]),
        "feasible_confirmation": infeasible_runs == 0,
    }
    # 只有冻结坐标和 confirmation 齐全时，门禁不通过才是方法层失败；
    # Provider、进程或缺失报告造成的 0-run 不能触发科学方向切换。
    evidence_complete = (
        completed >= int(gate["completed_runs_min"])
        and paired_seed_count >= int(gate["paired_seed_count_min"])
        and len(missing_keys) <= int(gate["missing_coordinates_max"])
    )
    passed = evidence_complete and all(checks.values())
    if not evidence_complete:
        status = "inconclusive"
        evidence_level = "inconclusive"
        next_action = gate.get(
            "next_if_inconclusive",
            "restore_valid_provider_credentials_and_rerun_same_frozen_coordinates",
        )
    elif passed:
        status = "passed"
        evidence_level = "tentative"
        next_action = gate["next_if_pass"]
    else:
        status = "failed"
        evidence_level = "tentative"
        next_action = gate["next_if_fail"]
    return {
        "schema_version": "cvrp_expert_router_proxy_analysis/v1",
        "suite": manifest["suite"],
        "manifest": str(manifest_path),
        "run_root": str(run_root),
        "status": status,
        "evidence_level": evidence_level,
        "metrics": {
            "completed_runs": completed,
            "valid_generated_runs": valid_generated_runs,
            "paired_seed_count": paired_seed_count,
            "confirmation_mean_improvement_vs_n2_pct": confirmation_mean_improvement,
            "environment_mean_degradation_pct": environment_mean_degradation_pct,
            "worst_environment_degradation_pct": worst_environment_degradation_pct,
            "runs_using_at_least_two_experts": runs_using_multiple_experts,
            "selector_invalid_outputs": selector_invalid_outputs,
            "missing_coordinates": len(missing_keys),
            "infeasible_confirmation_runs": infeasible_runs,
        },
        "checks": checks,
        "missing_run_keys": missing_keys,
        "run_evidence": run_evidence,
        "next_action": next_action,
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    lines = [
        "# CVRP Expert Router Proxy Gate",
        "",
        f"- suite: `{result['suite']}`",
        f"- status: `{result['status']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- next_action: `{result['next_action']}`",
        "",
        "## Metrics",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in metrics.items())
    lines.extend(["", "## Gate checks", ""])
    lines.extend(
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in result["checks"].items()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_proxy(args.manifest.resolve(), args.run_root.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_markdown(args.output_md, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
