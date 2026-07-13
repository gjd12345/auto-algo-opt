"""分析 TSP m3 深预算确认，要求训练与 Core-7 同时改善。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# 允许从仓库根目录直接运行本脚本，与其他正式分析入口保持一致。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_m3_operator_screen import _paired, load_rows


def analyze(rows: list[dict]) -> dict:
    """确认门槛同时约束产出、训练目标与 held-out，避免只看单一最好值。"""
    tsp_rows = [row for row in rows if row["problem"] == "tsp_construct"]
    baseline = [row for row in tsp_rows if row["arm"] == "four_ops"]
    candidate = [row for row in tsp_rows if row["arm"] == "with_m3"]
    baseline_rate = sum(row["valid"] for row in baseline) / len(baseline) if baseline else 0.0
    candidate_rate = sum(row["valid"] for row in candidate) / len(candidate) if candidate else 0.0
    m3_attempts = sum(row["m3_attempts"] for row in candidate)
    m3_outputs = sum(row["m3_outputs"] for row in candidate)
    m3_evaluated = sum(row["m3_evaluated"] for row in candidate)
    zero_output_runs = sum(
        row["m3_attempts"] == 0 or row["m3_outputs"] == 0 or row["m3_evaluated"] == 0
        for row in candidate
    )
    objective = _paired(tsp_rows, "tsp_construct", "objective")
    held_out = _paired(tsp_rows, "tsp_construct", "held_out")
    confirmed = (
        len(baseline) == 5
        and len(candidate) == 5
        and baseline_rate == 1.0
        and candidate_rate >= 0.9
        and zero_output_runs == 0
        and objective["complete_pairs"] == 5
        and held_out["complete_pairs"] == 5
        and (objective["median_gain"] or 0.0) > 0
        and objective["win"] >= 3
        and (held_out["median_gain"] or 0.0) > 0
        and held_out["win"] >= 3
    )
    return {
        "baseline_valid_rate": baseline_rate,
        "with_m3_valid_rate": candidate_rate,
        "m3_attempts": m3_attempts,
        "m3_outputs": m3_outputs,
        "m3_evaluated": m3_evaluated,
        "m3_output_rate": m3_outputs / m3_attempts if m3_attempts else 0.0,
        "m3_evaluated_rate": m3_evaluated / m3_attempts if m3_attempts else 0.0,
        "zero_output_runs": zero_output_runs,
        "objective_comparison": objective,
        "core7_comparison": held_out,
        "decision": {
            "status": "m3_tsp_confirmed" if confirmed else "m3_tsp_not_confirmed",
            "next_branch": "tsp_shared_evolution_control" if confirmed else "exclude_m3_from_shared_evolution",
        },
    }


def write_outputs(rows: list[dict], analysis: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with (output_dir / "m3_tsp_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "m3_tsp_summary.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = load_rows(args.suite_dir)
    analysis = analyze(rows)
    write_outputs(rows, analysis, args.output_dir)
    print(json.dumps(analysis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
