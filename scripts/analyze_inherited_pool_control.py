"""分析历史 top-6 热启动对短预算 TSP/CVRP 进化的影响。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


PROBLEMS = ("tsp_construct", "cvrp_construct")


def _held_out(report: dict) -> tuple[float | None, float]:
    entries = [value for value in report.values() if isinstance(value, dict)]
    feasible = [value for value in entries if value.get("feasible") is True]
    gaps = [float(value["relative_gap_pct"]) for value in feasible if isinstance(value.get("relative_gap_pct"), (int, float))]
    return (statistics.median(gaps) if gaps else None), (len(feasible) / len(entries) if entries else 0.0)


def _sample_count(run_dir: Path) -> int:
    """统计不重叠样本分片；用于解释热启动节省的生成调用，不计 best 副本。"""
    total = 0
    for path in (run_dir / "results" / "samples").glob("samples_*.json"):
        if path.name == "samples_best.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total += len(payload) if isinstance(payload, list) else 0
    return total


def load_rows(suite_dir: Path) -> list[dict]:
    index = json.loads((suite_dir / "run_index.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in index:
        summary_path = Path(item["output_dir"]) / "official_eoh_run_summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
        run = payload.get("run_summary") or {}
        objective = run.get("best_objective")
        held_out, feasible_rate = _held_out(run.get("held_out_report") or {})
        rows.append(
            {
                "problem": item["problem"],
                "arm": item["arm"],
                "seed": item["seed"],
                "status": item.get("status"),
                "objective": float(objective) if isinstance(objective, (int, float)) else None,
                "held_out": held_out,
                "held_out_feasible_rate": feasible_rate,
                "runtime_s": item.get("runtime_s"),
                "sample_count": _sample_count(Path(run.get("run_dir") or item["output_dir"])),
                "valid": isinstance(objective, (int, float)) and held_out is not None,
            }
        )
    return rows


def _paired(rows: list[dict], problem: str, field: str) -> dict:
    """正 gain 表示历史热启动的数值更低。"""
    selected = [row for row in rows if row["problem"] == problem and isinstance(row.get(field), (int, float))]
    by_key = {(row["arm"], row["seed"]): float(row[field]) for row in selected}
    gains: list[float] = []
    win = tie = loss = 0
    for seed in sorted({row["seed"] for row in selected}):
        fresh = by_key.get(("fresh_start", seed))
        inherited = by_key.get(("inherited_top6", seed))
        if fresh is None or inherited is None:
            continue
        gain = fresh - inherited
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
    results: dict[str, dict] = {}
    candidates = 0
    for problem in PROBLEMS:
        problem_rows = [row for row in rows if row["problem"] == problem]
        fresh = [row for row in problem_rows if row["arm"] == "fresh_start"]
        inherited = [row for row in problem_rows if row["arm"] == "inherited_top6"]
        fresh_rate = sum(row["valid"] for row in fresh) / len(fresh) if fresh else 0.0
        inherited_rate = sum(row["valid"] for row in inherited) / len(inherited) if inherited else 0.0
        objective = _paired(rows, problem, "objective")
        held_out = _paired(rows, problem, "held_out")
        runtime = _paired(rows, problem, "runtime_s")
        samples = _paired(rows, problem, "sample_count")
        candidate = (
            objective["complete_pairs"] == 3
            and held_out["complete_pairs"] == 3
            and inherited_rate >= fresh_rate - 0.1
            and (held_out["median_gain"] or 0.0) > 0
            and held_out["win"] >= 2
        )
        candidates += int(candidate)
        results[problem] = {
            "fresh_valid_rate": fresh_rate,
            "inherited_valid_rate": inherited_rate,
            "objective_comparison": objective,
            "held_out_comparison": held_out,
            "runtime_comparison": runtime,
            "sample_count_comparison": samples,
            "inheritance_candidate": candidate,
        }
    return {
        "problems": results,
        "decision": {
            "status": "inheritance_candidate" if candidates else "inheritance_not_supported",
            "candidate_problem_count": candidates,
            "next_branch": "offline_synthesis_and_no_more_llm" if candidates else "stop_shared_pool_experiment_line",
        },
    }


def write_outputs(rows: list[dict], analysis: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with (output_dir / "inheritance_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "inheritance_summary.json").write_text(
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
