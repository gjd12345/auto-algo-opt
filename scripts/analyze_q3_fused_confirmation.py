"""分析融合策略确认实验，报告三种规模的严格配对结果。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


METRICS = {
    "h1k": "hifo_1k_C100.pkl",
    "h5k": "hifo_5k_C100.pkl",
    "h10k": "hifo_10k_C100.pkl",
}


def _read_scores(summary_path: Path) -> dict[str, float | None]:
    """读取三档 held-out；缺失值保留为空，避免把失败误记为零。"""
    scores: dict[str, float | None] = {name: None for name in METRICS}
    if not summary_path.is_file():
        return scores
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return scores
    report = (payload.get("run_summary") or {}).get("held_out_report") or {}
    for name, filename in METRICS.items():
        for path, value in report.items():
            if str(path).endswith(filename) and isinstance(value, (int, float)):
                scores[name] = float(value)
                break
    return scores


def load_rows(suite_dir: Path) -> list[dict]:
    """把运行索引和 summary 合并，保留所有坐标及其有效性。"""
    rows = json.loads((suite_dir / "run_index.json").read_text(encoding="utf-8"))
    merged: list[dict] = []
    for row in rows:
        scores = _read_scores(Path(row["output_dir"]) / "official_eoh_run_summary.json")
        merged.append(
            {
                "problem": row.get("problem"),
                "arm": row.get("arm"),
                "seed": row.get("seed"),
                "status": row.get("status"),
                "attempts": row.get("attempts"),
                **scores,
                "valid": all(value is not None for value in scores.values()),
            }
        )
    return merged


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _compare(rows: list[dict], metric: str) -> dict:
    """同 seed 计算 sham - fused；正值表示融合策略的 gap 更低。"""
    by_key = {
        (row["arm"], row["seed"]): row[metric]
        for row in rows
        if row.get(metric) is not None
    }
    gains: list[float] = []
    seeds: list[int] = []
    win = tie = loss = 0
    for seed in sorted({row["seed"] for row in rows}):
        fused = by_key.get(("fused_sham", seed))
        sham = by_key.get(("sham_sham", seed))
        if fused is None or sham is None:
            continue
        gain = sham - fused
        gains.append(gain)
        seeds.append(seed)
        if gain > 0:
            win += 1
        elif gain < 0:
            loss += 1
        else:
            tie += 1
    return {
        "complete_pairs": len(gains),
        "paired_seeds": seeds,
        "median_gain": _median(gains),
        "win": win,
        "tie": tie,
        "loss": loss,
    }


def analyze(rows: list[dict]) -> dict:
    """主门禁只看预注册 5k；1k/10k 用于判断规模泛化。"""
    arms: dict[str, dict] = {}
    for arm in ("sham_sham", "fused_sham"):
        arm_rows = [row for row in rows if row["arm"] == arm]
        arms[arm] = {
            "coordinates": len(arm_rows),
            "fully_valid": sum(bool(row["valid"]) for row in arm_rows),
            "valid_rate": sum(bool(row["valid"]) for row in arm_rows) / len(arm_rows) if arm_rows else 0.0,
            "median_scores": {
                metric: _median([row[metric] for row in arm_rows if row.get(metric) is not None])
                for metric in METRICS
            },
        }
    comparisons = {metric: _compare(rows, metric) for metric in METRICS}
    primary = comparisons["h5k"]
    fused_rate = arms["fused_sham"]["valid_rate"]
    sham_rate = arms["sham_sham"]["valid_rate"]
    confirmed = (
        primary["complete_pairs"] >= 8
        and fused_rate >= 0.9
        and fused_rate >= sham_rate - 0.1
        and (primary["median_gain"] or 0.0) > 0
        and primary["win"] >= 6
    )
    cross_scale = confirmed and all(
        item["complete_pairs"] >= 8 and (item["median_gain"] or 0.0) >= 0
        for item in comparisons.values()
    )
    if confirmed:
        status = "confirmed_cross_scale" if cross_scale else "confirmed_primary_only"
        next_branch = "dynamic_selection_pilot" if cross_scale else "scale_failure_audit"
    else:
        status = "not_confirmed"
        next_branch = "q3_claim_revision"
    return {
        "primary_metric": "h5k",
        "arms": arms,
        "comparisons": comparisons,
        "decision": {"status": status, "next_branch": next_branch},
    }


def write_outputs(rows: list[dict], analysis: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["problem", "arm", "seed", "status", "attempts", *METRICS, "valid"]
    with (output_dir / "confirmation_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "confirmation_summary.json").write_text(
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
