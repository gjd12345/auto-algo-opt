"""Replay the frozen H-003 experiment into the offline preview data file."""

import json
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent_skill_loop.cvrp_workbench.pointwise_adapter import execute_pointwise_rule
from experiments.cvrp_midterm.analysis.eval_s2_holdout import (
    FROZEN_P0,
    FROZEN_V0,
    OUT_JSON,
    V0_DECOUPLED_CODE,
    compile_rule,
    paired_bootstrap_delta,
)


def replay(instance, rule, counterpart, checks):
    def compare(*args):
        chosen = rule(*args)
        if args[0] != args[1]:
            checks["states"] += 1
            checks["differences"] += int(chosen != counterpart(*args))
        return chosen

    outcome = execute_pointwise_rule(compare, instance, record_trace=False)
    if not outcome["valid"]:
        raise ValueError(f"{instance['instance_id']}: {outcome['error_detail']}")
    return outcome


def summarize(rows):
    left, right = zip(*(row["lengths"] for row in rows))
    comparison = paired_bootstrap_delta(list(right), list(left))
    return {"n": len(rows), "means": [mean(left), mean(right)], **comparison}


def main():
    frozen = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    baseline = compile_rule(FROZEN_V0.read_text(encoding="utf-8"), "V0")
    variant = compile_rule(V0_DECOUPLED_CODE, "V0_decoupled_theory")

    def replace_depot_only(*args):
        rule = variant if args[0] == args[1] else baseline
        return rule(*args)

    checks = {"states": 0, "differences": 0}
    rows = []
    depot_only_lengths = []
    by_size = {}
    frozen_comparisons = frozen["comparisons"]["V0_decoupled_vs_V0"]
    for size in (50, 100, 200):
        path = FROZEN_P0 / f"suite_{size}.json"
        instances = json.loads(path.read_text(encoding="utf-8"))["instances"]
        start = len(rows)
        for instance in instances:
            left = replay(instance, baseline, variant, checks)
            right = replay(instance, variant, baseline, checks)
            strict = execute_pointwise_rule(replace_depot_only, instance, record_trace=False)
            if not strict["valid"]:
                raise ValueError(f"{instance['instance_id']}: {strict['error_detail']}")
            depot_only_lengths.append(strict["tour_length"])
            rows.append({
                "id": instance["instance_id"],
                "size": size,
                "coords": [instance["depot"], *instance["customer_coordinates"]],
                "demands": [0, *instance["demands"]],
                "capacity": instance["capacity"],
                "lengths": [left["tour_length"], right["tour_length"]],
                "routes": [left["routes"], right["routes"]],
            })
        stats = summarize(rows[start:])
        if any(stats[key] != frozen_comparisons[f"p0_{size}"][key] for key in ("wtl", "rel_gain", "ci95")):
            raise ValueError(f"Replayed metrics differ from the archived n={size} evidence")
        by_size[size] = stats

    summary = summarize(rows)
    archived = frozen_comparisons["p0_all120"]
    if any(summary[key] != archived[key] for key in ("wtl", "rel_gain", "ci95")):
        raise ValueError("Replayed metrics differ from the archived P0-120 evidence")
    for actual, rule_id in zip(summary["means"], ("V0", "V0_decoupled_theory")):
        if round(actual, 4) != frozen["results"][rule_id]["p0_120_mean"]:
            raise ValueError(f"Replayed average differs from the archived {rule_id} evidence")

    examples = [row for row in rows if row["size"] == 50 and row["routes"][0][0][1] != row["routes"][1][0][1]]
    target = median(row["lengths"][0] - row["lengths"][1] for row in examples)
    example = min(examples, key=lambda row: abs(row["lengths"][0] - row["lengths"][1] - target))
    depot_only = {
        "mean": mean(depot_only_lengths),
        "rel_gain": paired_bootstrap_delta(depot_only_lengths, [row["lengths"][0] for row in rows])["rel_gain"],
        "changed_instances": sum(abs(value - row["lengths"][1]) > 1e-8 for row, value in zip(rows, depot_only_lengths)),
    }
    payload = {
        "summary": summary,
        "by_size": by_size,
        "checks": checks,
        "depot_only": depot_only,
        "example": example["id"],
        "instances": rows,
    }
    Path(__file__).with_name("data.js").write_text(
        "window.H003_PREVIEW = " + json.dumps(payload, separators=(",", ":"), allow_nan=False) + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Replayed {summary['n']} pairs; {checks}; example={example['id']}")


if __name__ == "__main__":
    main()
