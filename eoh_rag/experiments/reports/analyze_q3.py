#!/usr/bin/env python3
"""分析 Q3 BP 三臂消融的 held-out 结果。

兼容两种目录布局：

1. 当前 batch_runner：``<report>/<suite>/run_bp_online_<arm>_g*_r*/``；
2. 旧脚本：``<report>/<arm>/run_*/``。

若任一指定实验臂没有可用 held-out 分数，命令会返回非零状态，避免空分析被
误认为实验已形成结论。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


SUMMARY_FILENAME = "official_eoh_run_summary.json"


def _read_held_out_score(summary_path: Path, held_out_tag: str) -> float | None:
    """从单次运行摘要中提取匹配标签的有限数值分数。"""

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    held_out_report = (summary.get("run_summary") or {}).get("held_out_report") or {}
    if not isinstance(held_out_report, dict):
        return None

    for dataset_name, value in held_out_report.items():
        if held_out_tag in str(dataset_name) and isinstance(value, (int, float)):
            score = float(value)
            return score if math.isfinite(score) else None
    return None


def load_held_out_scores(arm_directory: str | Path, held_out_tag: str = "5k_C100") -> list[float]:
    """读取旧版 ``<arm>/run_*`` 目录中的 held-out 分数。"""

    arm_path = Path(arm_directory)
    scores: list[float] = []
    for summary_path in sorted(arm_path.glob(f"run_*/{SUMMARY_FILENAME}")):
        score = _read_held_out_score(summary_path, held_out_tag)
        if score is not None:
            scores.append(score)
    return scores


def discover_arm_summaries(report_directory: str | Path, arm: str) -> list[Path]:
    """发现指定实验臂的新旧布局摘要文件，并去除重复路径。"""

    report_path = Path(report_directory)
    discovered: set[Path] = set()

    # 旧布局：调用者传报告根目录，下面按 arm 分目录。
    discovered.update((report_path / arm).glob(f"run_*/{SUMMARY_FILENAME}"))

    # 新布局：batch_runner 把 arm 编入 run 标签，所有 run 平铺在 suite 目录。
    discovered.update(report_path.glob(f"run_*_{arm}_*/{SUMMARY_FILENAME}"))

    # 兼容调用者传 batch_runner 的 output 根目录，而不是已经拼好 suite 的目录。
    discovered.update(report_path.glob(f"*/run_*_{arm}_*/{SUMMARY_FILENAME}"))

    # 当前可复现实验按“问题/实验臂/seed”分层。保留显式层级匹配，避免递归扫描时
    # 把同一 formal 根目录下的失败批次或历史批次误并入正式样本。
    discovered.update(report_path.glob(f"*/{arm}/*/{SUMMARY_FILENAME}"))
    discovered.update(report_path.glob(f"*/*/{arm}/*/{SUMMARY_FILENAME}"))

    return sorted(path.resolve() for path in discovered if path.is_file())


def load_arm_scores(
    report_directory: str | Path,
    arm: str,
    held_out_tag: str = "5k_C100",
) -> list[float]:
    """按实验臂读取新旧两种布局中的 held-out 分数。"""

    scores: list[float] = []
    for summary_path in discover_arm_summaries(report_directory, arm):
        score = _read_held_out_score(summary_path, held_out_tag)
        if score is not None:
            scores.append(score)
    return scores


def _average_tied_ranks(values: np.ndarray) -> np.ndarray:
    """为绝对差值计算并列平均秩，供 Wilcoxon 近似检验使用。"""

    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        ranks[order[start:end]] = average_rank
        start = end
    return ranks


def paired_wilcoxon(left: list[float], right: list[float]) -> tuple[float, str]:
    """计算配对 Wilcoxon 正态近似；样本不足时返回可解释状态。"""

    if len(left) != len(right):
        return 1.0, "length_mismatch"

    differences = np.asarray(left, dtype=float) - np.asarray(right, dtype=float)
    nonzero = differences[differences != 0]
    if len(nonzero) < 2:
        return 1.0, "insufficient_nonzero_differences"

    ranks = _average_tied_ranks(np.abs(nonzero))
    positive_rank_sum = float(np.sum(ranks[nonzero > 0]))
    total_rank_sum = float(np.sum(ranks))
    statistic = min(positive_rank_sum, total_rank_sum - positive_rank_sum)
    sample_count = len(nonzero)
    mean = sample_count * (sample_count + 1) / 4.0
    standard_deviation = math.sqrt(
        sample_count * (sample_count + 1) * (2 * sample_count + 1) / 24.0
    )
    z_score = (statistic - mean) / standard_deviation if standard_deviation else 0.0
    p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    direction = "left_worse" if np.median(left) > np.median(right) else "left_better"
    return float(p_value), direction


def build_argument_parser() -> argparse.ArgumentParser:
    """构造分析命令参数。"""

    parser = argparse.ArgumentParser(description="Analyze Q3 BP held-out ablation results")
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--arms", nargs="+", default=["pure", "generic", "answer"])
    parser.add_argument("--held-out", default="5k_C100")
    return parser


def main(argv: list[str] | None = None) -> int:
    """输出三臂分数、配对检验和裁决表；数据不足时明确失败。"""

    args = build_argument_parser().parse_args(argv)
    report_path = Path(args.report_dir)
    scores: dict[str, list[float]] = {}

    for arm in args.arms:
        arm_scores = load_arm_scores(report_path, arm, args.held_out)
        scores[arm] = arm_scores
        if arm_scores:
            print(
                f"{arm}: n={len(arm_scores):2d}  median={np.median(arm_scores):.4f}  "
                f"scores={[round(value, 4) for value in arm_scores]}"
            )
        else:
            print(f"{arm}: n= 0  median=N/A  scores=[]")

    missing_arms = [arm for arm, arm_scores in scores.items() if not arm_scores]
    if missing_arms:
        print(
            "ERROR: no held-out scores found for arm(s): " + ", ".join(missing_arms),
            file=sys.stderr,
        )
        print(
            f"Checked current batch_runner and legacy directory layouts under: {report_path.resolve()}",
            file=sys.stderr,
        )
        return 1

    if all(arm in scores for arm in ("pure", "generic", "answer")):
        pure_answer_p, pure_answer_direction = paired_wilcoxon(
            scores["pure"], scores["answer"]
        )
        pure_generic_p, pure_generic_direction = paired_wilcoxon(
            scores["pure"], scores["generic"]
        )
        generic_answer_p, generic_answer_direction = paired_wilcoxon(
            scores["generic"], scores["answer"]
        )
        print("\n=== Wilcoxon paired tests ===")
        print(
            f"pure vs answer:  p={pure_answer_p:.4f}  direction={pure_answer_direction}"
        )
        print(
            f"pure vs generic: p={pure_generic_p:.4f}  direction={pure_generic_direction}"
        )
        print(
            f"generic vs answer: p={generic_answer_p:.4f}  direction={generic_answer_direction}"
        )

    print(f"\n=== Decision table ({args.held_out}) ===")
    print("| arm | n | median |")
    print("|-----|---|--------|")
    for arm in args.arms:
        print(f"| {arm:10s} | {len(scores[arm]):2d} | {np.median(scores[arm]):.4f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
