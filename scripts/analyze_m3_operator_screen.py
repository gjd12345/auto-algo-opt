"""分析三问题 m3 算子筛查，重点报告产出率、有效率和配对目标值。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path


PROBLEMS = ("bp_online", "tsp_construct", "cvrp_construct")


def _held_out_summary(problem: str, report: dict) -> tuple[float | None, float]:
    """压缩各问题 held-out；数值越低越好，同时返回可行实例比例。"""
    if problem == "bp_online":
        for path, value in report.items():
            if str(path).endswith("hifo_5k_C100.pkl") and isinstance(value, (int, float)):
                return float(value), 1.0
        return None, 0.0
    entries = [value for value in report.values() if isinstance(value, dict)]
    feasible = [value for value in entries if value.get("feasible") is True]
    gaps = [float(value["relative_gap_pct"]) for value in feasible if isinstance(value.get("relative_gap_pct"), (int, float))]
    return (statistics.median(gaps) if gaps else None), (len(feasible) / len(entries) if entries else 0.0)


def _operator_counts(run_dir: Path) -> dict[str, int]:
    """样本文件按区间分片且不重叠；跳过 best 文件，避免重复计数。"""
    counts: Counter[str] = Counter()
    sample_dir = run_dir / "results" / "samples"
    for path in sorted(sample_dir.glob("samples_*.json")):
        if path.name == "samples_best.json":
            continue
        try:
            samples = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for sample in samples if isinstance(samples, list) else []:
            if sample.get("operator") != "m3":
                continue
            counts["m3_attempts"] += 1
            if sample.get("code") and sample.get("algorithm"):
                counts["m3_outputs"] += 1
            if isinstance(sample.get("objective"), (int, float)):
                counts["m3_evaluated"] += 1
    return dict(counts)


def load_rows(suite_dir: Path) -> list[dict]:
    """读取每个正式坐标，不用缺失结果填零。"""
    index = json.loads((suite_dir / "run_index.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in index:
        summary_path = Path(item["output_dir"]) / "official_eoh_run_summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
        run = payload.get("run_summary") or {}
        objective = run.get("best_objective")
        held_out, feasible_rate = _held_out_summary(item["problem"], run.get("held_out_report") or {})
        counts = _operator_counts(Path(run.get("run_dir") or item["output_dir"]))
        rows.append(
            {
                "problem": item["problem"],
                "arm": item["arm"],
                "seed": item["seed"],
                "status": item.get("status"),
                "attempts": item.get("attempts"),
                "objective": float(objective) if isinstance(objective, (int, float)) else None,
                "held_out": held_out,
                "held_out_feasible_rate": feasible_rate,
                "m3_attempts": counts.get("m3_attempts", 0),
                "m3_outputs": counts.get("m3_outputs", 0),
                "m3_evaluated": counts.get("m3_evaluated", 0),
                "valid": isinstance(objective, (int, float)),
            }
        )
    return rows


def _paired(rows: list[dict], problem: str, field: str) -> dict:
    """正 gain 表示加入 m3 后目标值更低。"""
    selected = [row for row in rows if row["problem"] == problem and row.get(field) is not None]
    by_key = {(row["arm"], row["seed"]): row[field] for row in selected}
    gains: list[float] = []
    win = tie = loss = 0
    for seed in sorted({row["seed"] for row in selected}):
        baseline = by_key.get(("four_ops", seed))
        candidate = by_key.get(("with_m3", seed))
        if baseline is None or candidate is None:
            continue
        gain = baseline - candidate
        gains.append(gain)
        if gain > 0:
            win += 1
        elif gain < 0:
            loss += 1
        else:
            tie += 1
    return {
        "complete_pairs": len(gains),
        "median_gain": statistics.median(gains) if gains else None,
        "win": win,
        "tie": tie,
        "loss": loss,
    }


def analyze(rows: list[dict]) -> dict:
    problems: dict[str, dict] = {}
    contract_failed = False
    positive_problems = 0
    for problem in PROBLEMS:
        problem_rows = [row for row in rows if row["problem"] == problem]
        baseline = [row for row in problem_rows if row["arm"] == "four_ops"]
        candidate = [row for row in problem_rows if row["arm"] == "with_m3"]
        m3_attempts = sum(row["m3_attempts"] for row in candidate)
        m3_outputs = sum(row["m3_outputs"] for row in candidate)
        m3_evaluated = sum(row["m3_evaluated"] for row in candidate)
        zero_output_runs = sum(row["m3_attempts"] > 0 and row["m3_outputs"] == 0 for row in candidate)
        baseline_rate = sum(row["valid"] for row in baseline) / len(baseline) if baseline else 0.0
        candidate_rate = sum(row["valid"] for row in candidate) / len(candidate) if candidate else 0.0
        objective = _paired(rows, problem, "objective")
        held_out = _paired(rows, problem, "held_out")
        contract_ok = (
            len(candidate) == 3
            and m3_attempts > 0
            and m3_outputs > 0
            and m3_evaluated > 0
            and zero_output_runs == 0
            and candidate_rate >= baseline_rate - 0.1
        )
        contract_failed = contract_failed or not contract_ok
        positive_problems += int((objective["median_gain"] or 0.0) > 0)
        problems[problem] = {
            "baseline_valid_rate": baseline_rate,
            "with_m3_valid_rate": candidate_rate,
            "m3_attempts": m3_attempts,
            "m3_outputs": m3_outputs,
            "m3_evaluated": m3_evaluated,
            "m3_output_rate": m3_outputs / m3_attempts if m3_attempts else 0.0,
            "m3_evaluated_rate": m3_evaluated / m3_attempts if m3_attempts else 0.0,
            "zero_output_runs": zero_output_runs,
            "objective_comparison": objective,
            "held_out_comparison": held_out,
            "contract_ok": contract_ok,
        }
    if contract_failed:
        decision = {"status": "m3_contract_failed", "next_branch": "exclude_m3_and_audit"}
    elif positive_problems >= 2:
        decision = {"status": "m3_candidate", "next_branch": "m3_confirmation_or_shared_control"}
    else:
        decision = {"status": "m3_productive_no_broad_effect", "next_branch": "exclude_m3_from_shared_evolution"}
    return {"problems": problems, "decision": decision}


def write_outputs(rows: list[dict], analysis: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with (output_dir / "m3_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "m3_summary.json").write_text(
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
