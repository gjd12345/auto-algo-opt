"""确定性探测 TSP 搜索控制器 DSL 的开发集可达上限。"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

from eoh_rag.search_control.controller_seed_factory import (
    BASELINE_PLAN,
    Plan,
    generate_random_plan,
)
from eoh_rag.search_control.tsp_controller import (
    MAX_TOTAL_BUDGET,
    PLAN_COST_PENALTY,
    build_controller_suite,
    evaluate_controller,
)


def _instance_score(result: dict[str, Any]) -> float:
    return float(result["normalized_cost"]) + PLAN_COST_PENALTY * (
        float(result["executed_weighted_budget"]) / MAX_TOTAL_BUDGET
    )


def _plan_payload(plan: Plan) -> list[list[object]]:
    return [[primitive, budget, threshold] for primitive, budget, threshold in plan]


def probe_controller_space(
    *,
    sample_count: int,
    random_seed: int,
    suite_name: str = "synthetic_dev_v1",
    split_thresholds: Sequence[int] = (80, 96, 112, 128),
) -> dict[str, Any]:
    """比较固定计划和两段式规模计划；确认集不在本函数接口中。"""

    if sample_count < 1:
        raise ValueError("sample_count 必须大于 0")
    suite = build_controller_suite(suite_name)
    rng = random.Random(random_seed)
    plans: list[Plan] = [BASELINE_PLAN]
    seen = {BASELINE_PLAN}
    while len(plans) < sample_count + 1:
        plan = generate_random_plan(rng)
        if plan in seen:
            continue
        plans.append(plan)
        seen.add(plan)

    evaluated: list[dict[str, Any]] = []
    for plan in plans:
        summary = evaluate_controller(lambda size, budget, value=plan: value, suite)
        evaluated.append(
            {
                "plan": plan,
                "objective": float(summary["objective"]),
                "instance_scores": [
                    _instance_score(item) for item in summary["instance_results"]
                ],
            }
        )

    baseline = evaluated[0]
    best_fixed = min(evaluated, key=lambda item: item["objective"])
    branch_candidates: list[dict[str, Any]] = []
    node_counts = [len(instance.initial_route) for instance in suite]
    for threshold in split_thresholds:
        small_indices = [index for index, size in enumerate(node_counts) if size <= threshold]
        large_indices = [index for index, size in enumerate(node_counts) if size > threshold]
        if not small_indices or not large_indices:
            continue

        best_small = min(
            evaluated,
            key=lambda item: fmean(item["instance_scores"][index] for index in small_indices),
        )
        best_large = min(
            evaluated,
            key=lambda item: fmean(item["instance_scores"][index] for index in large_indices),
        )

        def size_aware_plan(
            problem_size: int,
            total_budget: int,
            *,
            split: int = threshold,
            small_plan: Plan = best_small["plan"],
            large_plan: Plan = best_large["plan"],
        ) -> Plan:
            del total_budget
            return small_plan if problem_size <= split else large_plan

        summary = evaluate_controller(size_aware_plan, suite)
        branch_candidates.append(
            {
                "controller_type": "size_branch",
                "threshold": threshold,
                "objective": float(summary["objective"]),
                "small_plan": best_small["plan"],
                "large_plan": best_large["plan"],
            }
        )

    best_branch = min(branch_candidates, key=lambda item: item["objective"])
    fixed_payload = {
        "controller_type": "fixed",
        "objective": best_fixed["objective"],
        "plan": best_fixed["plan"],
    }
    selected = min(
        [fixed_payload, best_branch],
        key=lambda item: float(item["objective"]),
    )

    def serialize_controller(item: dict[str, Any]) -> dict[str, Any]:
        payload = dict(item)
        if "plan" in payload:
            payload["plan"] = _plan_payload(payload["plan"])
        if "small_plan" in payload:
            payload["small_plan"] = _plan_payload(payload["small_plan"])
        if "large_plan" in payload:
            payload["large_plan"] = _plan_payload(payload["large_plan"])
        return payload

    return {
        "actor": "codex_exploration",
        "asset_role": "external_teacher_probe",
        "selection_suite": suite_name,
        "confirm_suite_used": False,
        "random_seed": random_seed,
        "random_sample_count": sample_count,
        "evaluated_plan_count": len(evaluated),
        "split_thresholds": list(split_thresholds),
        "baseline": {
            "objective": baseline["objective"],
            "plan": _plan_payload(BASELINE_PLAN),
        },
        "best_fixed": serialize_controller(fixed_payload),
        "best_size_branch": serialize_controller(best_branch),
        "selected_controller": serialize_controller(selected),
        "absolute_objective_improvement": (
            float(baseline["objective"]) - float(selected["objective"])
        ),
        "relative_objective_improvement_pct": (
            (float(baseline["objective"]) - float(selected["objective"]))
            / abs(float(baseline["objective"]))
            * 100.0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the dev-only TSP controller space")
    parser.add_argument("--sample-count", type=int, default=2000)
    parser.add_argument("--random-seed", type=int, default=20260715)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = probe_controller_space(
        sample_count=args.sample_count,
        random_seed=args.random_seed,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
