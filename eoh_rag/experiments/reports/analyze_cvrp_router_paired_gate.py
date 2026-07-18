"""裁决 CVRP router 两臂配对实验，严格使用 manifest 中的冻结门槛。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from eoh_rag.experiments.reports.analyze_cvrp_expert_router import (
    _expected_run_keys,
    _load_json,
    _valid_generated_sample_count,
)


CONTROL_ARM = "router_aware_control"
MEMORY_ARM = "reevo_inspired_memory"
SUCCESS_STATUSES = {"ok", "skipped_complete"}


def _resolve_run_dir(run_root: Path, row: dict[str, Any]) -> Path:
    """优先使用账本路径；跨设备重放时退回到 run_root 下的稳定相对布局。"""
    recorded = Path(str(row.get("output_dir", "")))
    if recorded.is_dir():
        return recorded
    return (
        run_root
        / str(row["problem"])
        / str(row["arm"])
        / str(row["seed"])
    )


def _empty_arm_accumulator() -> dict[str, Any]:
    return {
        "completed_runs": 0,
        "valid_generated_runs": 0,
        "confirmation_improvements": [],
        "environment_degradations": {},
        "runs_using_at_least_two_experts": 0,
        "selector_invalid_outputs": 0,
        "infeasible_confirmation_runs": 0,
    }


def _summarize_arm(accumulator: dict[str, Any]) -> dict[str, Any]:
    environment_means = {
        name: mean(values)
        for name, values in sorted(accumulator["environment_degradations"].items())
    }
    return {
        "completed_runs": accumulator["completed_runs"],
        "valid_generated_runs": accumulator["valid_generated_runs"],
        "confirmation_mean_improvement_vs_n2_pct": (
            mean(accumulator["confirmation_improvements"])
            if accumulator["confirmation_improvements"]
            else None
        ),
        "environment_mean_degradation_pct": environment_means,
        "worst_environment_degradation_pct": (
            max(environment_means.values()) if environment_means else None
        ),
        "runs_using_at_least_two_experts": accumulator[
            "runs_using_at_least_two_experts"
        ],
        "selector_invalid_outputs": accumulator["selector_invalid_outputs"],
        "infeasible_confirmation_runs": accumulator[
            "infeasible_confirmation_runs"
        ],
    }


def _validate_manifest(manifest: dict[str, Any]) -> None:
    arm_names = [arm.get("name") for arm in manifest.get("arms", [])]
    if arm_names != [CONTROL_ARM, MEMORY_ARM]:
        raise ValueError(
            "paired CVRP router manifest must contain the frozen control and memory arms"
        )
    if len(manifest.get("generations", [])) != 1:
        raise ValueError("paired CVRP router gate requires exactly one generation budget")
    if "paired_gate" not in manifest:
        raise ValueError("paired CVRP router manifest is missing paired_gate")


def analyze_paired_gate(manifest_path: Path, run_root: Path) -> dict[str, Any]:
    """聚合完整配对并裁决；缺失坐标只能得到 inconclusive，不能伪装方法失败。"""
    manifest = _load_json(manifest_path)
    _validate_manifest(manifest)
    gate = manifest["paired_gate"]
    index_path = run_root / "run_index.json"
    rows = _load_json(index_path) if index_path.is_file() else []
    rows_by_key = {
        row.get("run_key"): row
        for row in rows
        if isinstance(row, dict) and row.get("run_key")
    }
    expected_keys = _expected_run_keys(manifest)
    missing_keys = sorted(expected_keys - set(rows_by_key))

    arm_accumulators = {
        CONTROL_ARM: _empty_arm_accumulator(),
        MEMORY_ARM: _empty_arm_accumulator(),
    }
    successful_by_seed: dict[int, dict[str, float]] = {}
    run_evidence: list[dict[str, Any]] = []

    for run_key in sorted(expected_keys):
        row = rows_by_key.get(run_key)
        if not row:
            continue
        arm_name = str(row.get("arm", ""))
        if arm_name not in arm_accumulators:
            run_evidence.append(
                {"run_key": run_key, "status": "unexpected_arm", "arm": arm_name}
            )
            continue
        if row.get("status") not in SUCCESS_STATUSES:
            run_evidence.append(
                {"run_key": run_key, "status": row.get("status", "unknown")}
            )
            continue

        run_dir = _resolve_run_dir(run_root, row)
        summary_path = run_dir / "official_eoh_run_summary.json"
        if not summary_path.is_file():
            run_evidence.append({"run_key": run_key, "status": "missing_summary"})
            continue
        summary = _load_json(summary_path)
        run_summary = summary.get("run_summary") or {}
        confirmation = run_summary.get("confirmation_report") or {}
        if not run_summary.get("ok") or not confirmation:
            run_evidence.append(
                {"run_key": run_key, "status": "invalid_summary_or_confirmation"}
            )
            continue

        accumulator = arm_accumulators[arm_name]
        accumulator["completed_runs"] += 1
        generated_count = _valid_generated_sample_count(run_dir)
        if generated_count > 0:
            accumulator["valid_generated_runs"] += 1

        improvement = float(confirmation["mean_improvement_vs_n2_pct"])
        accumulator["confirmation_improvements"].append(improvement)
        for environment, relative_cost in (
            confirmation.get("environment_relative_cost_vs_n2") or {}
        ).items():
            accumulator["environment_degradations"].setdefault(
                environment, []
            ).append(100.0 * float(relative_cost))

        counts = confirmation.get("expert_selection_counts") or {}
        used_experts = sorted(
            expert_id for expert_id, count in counts.items() if int(count) > 0
        )
        if len(used_experts) >= 2:
            accumulator["runs_using_at_least_two_experts"] += 1
        invalid_outputs = int(confirmation.get("selector_invalid_outputs", 0))
        accumulator["selector_invalid_outputs"] += invalid_outputs
        feasible = bool((confirmation.get("evaluation_result") or {}).get("feasible"))
        if not feasible:
            accumulator["infeasible_confirmation_runs"] += 1

        seed = int(row["seed"])
        successful_by_seed.setdefault(seed, {})[arm_name] = improvement
        run_evidence.append(
            {
                "run_key": run_key,
                "status": "ok",
                "arm": arm_name,
                "seed": seed,
                "valid_generated_samples": generated_count,
                "confirmation_improvement_vs_n2_pct": improvement,
                "used_experts": used_experts,
                "selector_invalid_outputs": invalid_outputs,
                "feasible": feasible,
            }
        )

    paired_deltas = {
        str(seed): values[MEMORY_ARM] - values[CONTROL_ARM]
        for seed, values in sorted(successful_by_seed.items())
        if CONTROL_ARM in values and MEMORY_ARM in values
    }
    arm_metrics = {
        arm_name: _summarize_arm(accumulator)
        for arm_name, accumulator in arm_accumulators.items()
    }
    completed_runs = sum(item["completed_runs"] for item in arm_metrics.values())
    valid_generated_runs = sum(
        item["valid_generated_runs"] for item in arm_metrics.values()
    )
    paired_seed_count = len(paired_deltas)
    paired_mean_delta = mean(paired_deltas.values()) if paired_deltas else None
    memory_metrics = arm_metrics[MEMORY_ARM]
    total_invalid_outputs = sum(
        item["selector_invalid_outputs"] for item in arm_metrics.values()
    )
    total_infeasible_runs = sum(
        item["infeasible_confirmation_runs"] for item in arm_metrics.values()
    )

    checks = {
        "completed_runs": completed_runs >= int(gate["completed_runs_min"]),
        "valid_generated_runs": valid_generated_runs
        >= int(gate["valid_generated_runs_min"]),
        "paired_seed_count": paired_seed_count >= int(gate["paired_seed_count_min"]),
        "memory_minus_control_confirmation_improvement": paired_mean_delta is not None
        and paired_mean_delta
        >= float(gate["memory_minus_control_confirmation_improvement_pct_min"]),
        "memory_confirmation_mean_improvement": memory_metrics[
            "confirmation_mean_improvement_vs_n2_pct"
        ]
        is not None
        and memory_metrics["confirmation_mean_improvement_vs_n2_pct"]
        >= float(gate["memory_confirmation_mean_improvement_vs_n2_pct_min"]),
        "memory_confirmation_environment_degradation": memory_metrics[
            "worst_environment_degradation_pct"
        ]
        is not None
        and memory_metrics["worst_environment_degradation_pct"]
        <= float(gate["memory_confirmation_environment_degradation_pct_max"]),
        "memory_multi_expert_usage": memory_metrics[
            "runs_using_at_least_two_experts"
        ]
        >= int(gate["memory_runs_using_at_least_two_experts_min"]),
        "selector_invalid_outputs": total_invalid_outputs
        <= int(gate["selector_invalid_outputs_max"]),
        "missing_coordinates": len(missing_keys)
        <= int(gate["missing_coordinates_max"]),
        "feasible_confirmation": total_infeasible_runs == 0,
    }
    # 只有全部冻结坐标、生成样本和 confirmation 都齐全时，门禁失败才是方法负结果。
    evidence_complete = (
        checks["completed_runs"]
        and checks["valid_generated_runs"]
        and checks["paired_seed_count"]
        and checks["missing_coordinates"]
        and checks["feasible_confirmation"]
    )
    passed = evidence_complete and all(checks.values())
    if not evidence_complete:
        status = "inconclusive"
        evidence_level = "inconclusive"
        next_action = gate.get(
            "next_if_inconclusive",
            "restore_incomplete_frozen_coordinates_without_changing_the_cohort",
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
        "schema_version": "cvrp_router_paired_gate_analysis/v1",
        "suite": manifest["suite"],
        "manifest": str(manifest_path),
        "run_root": str(run_root),
        "status": status,
        "evidence_level": evidence_level,
        "metrics": {
            "completed_runs": completed_runs,
            "valid_generated_runs": valid_generated_runs,
            "paired_seed_count": paired_seed_count,
            "memory_minus_control_confirmation_improvement_pct": paired_mean_delta,
            "paired_deltas_by_seed_pct": paired_deltas,
            "selector_invalid_outputs": total_invalid_outputs,
            "missing_coordinates": len(missing_keys),
            "infeasible_confirmation_runs": total_infeasible_runs,
            "arms": arm_metrics,
        },
        "checks": checks,
        "missing_run_keys": missing_keys,
        "run_evidence": run_evidence,
        "next_action": next_action,
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    lines = [
        "# CVRP Router Paired Gate",
        "",
        f"- suite: `{result['suite']}`",
        f"- status: `{result['status']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- next_action: `{result['next_action']}`",
        "",
        "## Paired metrics",
        "",
        f"- completed_runs: `{metrics['completed_runs']}`",
        f"- valid_generated_runs: `{metrics['valid_generated_runs']}`",
        f"- paired_seed_count: `{metrics['paired_seed_count']}`",
        "- memory_minus_control_confirmation_improvement_pct: "
        f"`{metrics['memory_minus_control_confirmation_improvement_pct']}`",
        f"- missing_coordinates: `{metrics['missing_coordinates']}`",
        "",
        "## Arm metrics",
        "",
    ]
    for arm_name, arm_metrics in metrics["arms"].items():
        lines.append(f"### {arm_name}")
        lines.append("")
        lines.extend(f"- {key}: `{value}`" for key, value in arm_metrics.items())
        lines.append("")
    lines.extend(["## Gate checks", ""])
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
    result = analyze_paired_gate(args.manifest.resolve(), args.run_root.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_markdown(args.output_md, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
