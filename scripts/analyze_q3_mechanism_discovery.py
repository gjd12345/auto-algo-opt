"""分析 Q3 机制发现实验，输出逐臂中位数、严格配对和自动分支。"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


PRIMARY_HELD_OUT = "hifo_5k_C100.pkl"
COMPARISONS = [
    ("api_only_vs_pure_eoh", "api_only", "pure_eoh"),
    ("sham_sham_vs_api_only", "sham_sham", "api_only"),
    ("harmonic_residual_vs_sham_sham", "harmonic_residual", "sham_sham"),
    ("harmonic_residual_vs_harmonic_sham", "harmonic_residual", "harmonic_sham"),
    ("harmonic_residual_vs_sham_residual", "harmonic_residual", "sham_residual"),
    ("fused_sham_vs_harmonic_residual", "fused_sham", "harmonic_residual"),
]


def _read_primary_score(summary_path: Path) -> float | None:
    """读取主 held-out 分数；缺失或非数值时保留为空，不纳入效果中位数。"""
    if not summary_path.is_file():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    report = (payload.get("run_summary") or {}).get("held_out_report") or {}
    for path, value in report.items():
        if str(path).endswith(PRIMARY_HELD_OUT) and isinstance(value, (int, float)):
            return float(value)
    return None


def load_rows(suite_dir: Path) -> list[dict]:
    """把运行索引与 summary 合并成稳定的逐坐标表。"""
    index_path = suite_dir / "run_index.json"
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    merged: list[dict] = []
    for row in rows:
        score = _read_primary_score(Path(row["output_dir"]) / "official_eoh_run_summary.json")
        merged.append(
            {
                "problem": row.get("problem"),
                "arm": row.get("arm"),
                "seed": row.get("seed"),
                "status": row.get("status"),
                "attempts": row.get("attempts"),
                "score": score,
                "valid": score is not None,
            }
        )
    return merged


def _arm_summary(rows: list[dict]) -> dict[str, dict]:
    summaries: dict[str, dict] = {}
    for arm in sorted({row["arm"] for row in rows}):
        arm_rows = [row for row in rows if row["arm"] == arm]
        scores = [row["score"] for row in arm_rows if row["score"] is not None]
        summaries[arm] = {
            "coordinates": len(arm_rows),
            "valid_scores": len(scores),
            "valid_rate": len(scores) / len(arm_rows) if arm_rows else 0.0,
            "median_score": statistics.median(scores) if scores else None,
        }
    return summaries


def _paired_comparison(rows: list[dict], candidate: str, reference: str) -> dict:
    """同 seed 比较两个臂；正 gain 表示 candidate 的 gap 更低。"""
    by_key = {(row["arm"], row["seed"]): row["score"] for row in rows if row["score"] is not None}
    seeds = sorted({row["seed"] for row in rows})
    gains: list[float] = []
    win = tie = loss = 0
    paired_seeds: list[int] = []
    for seed in seeds:
        candidate_score = by_key.get((candidate, seed))
        reference_score = by_key.get((reference, seed))
        if candidate_score is None or reference_score is None:
            continue
        gain = reference_score - candidate_score
        gains.append(gain)
        paired_seeds.append(seed)
        if gain > 0:
            win += 1
        elif gain < 0:
            loss += 1
        else:
            tie += 1
    return {
        "candidate": candidate,
        "reference": reference,
        "paired_seeds": paired_seeds,
        "complete_pairs": len(gains),
        "median_gain": statistics.median(gains) if gains else None,
        "win": win,
        "tie": tie,
        "loss": loss,
    }


def _decision(arms: dict[str, dict], comparisons: dict[str, dict]) -> dict:
    """按预注册门禁选择下一轮唯一分支，不使用事后最佳样本。"""
    required = [
        comparisons["harmonic_residual_vs_sham_sham"],
        comparisons["harmonic_residual_vs_harmonic_sham"],
        comparisons["harmonic_residual_vs_sham_residual"],
    ]
    if arms.get("harmonic_residual", {}).get("valid_rate", 0.0) < 0.8 or any(
        item["complete_pairs"] < 4 for item in required
    ):
        return {"status": "inconclusive_failure_contract", "next_branch": "failure_diagnosis"}

    pair_vs_sham, pair_vs_harmonic, pair_vs_residual = required
    semantic_candidate = (
        pair_vs_sham["median_gain"] > 0
        and pair_vs_harmonic["median_gain"] > 0
        and pair_vs_residual["median_gain"] > 0
        and pair_vs_sham["win"] >= 3
    )
    if semantic_candidate:
        fused = comparisons["fused_sham_vs_harmonic_residual"]
        fused_equivalent = fused["complete_pairs"] >= 4 and abs(fused["median_gain"] or 0.0) <= 0.25
        return {
            "status": "semantic_interaction_candidate",
            "next_branch": "semantic_confirmation",
            "fused_practically_equivalent": fused_equivalent,
        }

    sham = comparisons["sham_sham_vs_api_only"]
    if sham["complete_pairs"] >= 4 and (sham["median_gain"] or 0.0) > 0:
        return {"status": "context_effect_candidate", "next_branch": "context_control_confirmation"}
    return {"status": "no_clear_mechanism", "next_branch": "failure_and_behavior_audit"}


def analyze(rows: list[dict]) -> dict:
    arms = _arm_summary(rows)
    comparisons = {
        name: _paired_comparison(rows, candidate, reference)
        for name, candidate, reference in COMPARISONS
    }
    return {"primary_metric": PRIMARY_HELD_OUT, "arms": arms, "comparisons": comparisons, "decision": _decision(arms, comparisons)}


def write_outputs(rows: list[dict], analysis: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "mechanism_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["problem", "arm", "seed", "status", "attempts", "score", "valid"])
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "mechanism_summary.json").write_text(
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
