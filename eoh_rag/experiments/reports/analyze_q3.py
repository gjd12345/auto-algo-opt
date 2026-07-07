#!/usr/bin/env python3
"""Q3 BP 消融分析脚本:Wilcoxon 配对检验 + 裁决表 + held-out 对比。

用法:
  python3 analyze_q3.py \
    --report-dir eoh_rag_workspace/reports/bp_ablation_q3 \
    --arms pure generic answer \
    --held-out 5k_C100

依赖:scipy(可选,无则用近似)
输出:裁决表(含 median + p-value + direction)
"""
from __future__ import annotations
import argparse, json, sys, os
from pathlib import Path
import numpy as np

def load_held_out_scores(arm_dir: str, held_out_tag: str = "5k_C100") -> list[float]:
    """从每 run 的 summary 中提取 held-out 分数。"""
    scores = []
    arm_path = Path(arm_dir)
    for run_dir in sorted(arm_path.glob("run_*")):
        summary_file = run_dir / "official_eoh_run_summary.json"
        if not summary_file.exists():
            continue
        summary = json.loads(summary_file.read_text())
        run_summary = summary.get("run_summary", {})
        held_out = run_summary.get("held_out_report", {})
        # 取包含 held_out_tag 的项的值
        val = None
        for k, v in held_out.items():
            if held_out_tag in k:
                val = v
                break
        if val is not None and isinstance(val, (int, float)) and np.isfinite(val):
            scores.append(val)
    return scores

def paired_wilcoxon(a: list[float], b: list[float]) -> tuple:
    """配对 Wilcoxon signed-rank 检验(纯 NumPy 实现,无 scipy 依赖)。"""
    if len(a) != len(b):
        return 1.0, "length mismatch"
    diffs = np.array(a) - np.array(b)
    nonzero = diffs[diffs != 0]
    if len(nonzero) < 2:
        return 1.0, "insufficient nonzero diffs"
    ranks = np.argsort(np.abs(nonzero)) + 1
    signed = np.sum(ranks[nonzero > 0])  # R+
    n = len(nonzero)
    w = min(signed, n*(n+1)//2 - signed)
    # 近似正态(适用于 n>=10)
    mu = n*(n+1)/4
    sigma = np.sqrt(n*(n+1)*(2*n+1)/24)
    z = (w - mu) / sigma if sigma > 0 else 0
    p = 2 * (1 - 0.5 * (1 + np.math.erf(abs(z) / np.sqrt(2))))  # two-tailed
    direction = "pure_worse" if np.median(a) > np.median(b) else "pure_better"
    return float(p), direction

def main():
    parser = argparse.ArgumentParser(description="Q3 消融分析")
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--arms", nargs="+", default=["pure", "generic", "answer"])
    parser.add_argument("--held-out", default="5k_C100")
    args = parser.parse_args()

    base = Path(args.report_dir)
    scores = {}
    for arm in args.arms:
        arm_dir = base / arm
        if not arm_dir.exists():
            print(f"[WARN] {arm_dir} not found, skip")
            continue
        s = load_held_out_scores(str(arm_dir), args.held_out)
        scores[arm] = s
        print(f"{arm}: n={len(s):2d}  median={np.median(s):.4f}  scores={[round(x,4) for x in s]}")

    # 配对检验
    if "pure" in scores and "answer" in scores and "generic" in scores:
        p_pa, dir_pa = paired_wilcoxon(scores["pure"], scores["answer"])
        p_pg, dir_pg = paired_wilcoxon(scores["pure"], scores["generic"])
        p_ga, dir_ga = paired_wilcoxon(scores["generic"], scores["answer"])
        print(f"\n=== Wilcoxon 配对检验 ===")
        print(f"pure vs answer:  p={p_pa:.4f}  direction={dir_pa}")
        print(f"pure vs generic: p={p_pg:.4f}  direction={dir_pg}")
        print(f"generic vs answer: p={p_ga:.4f}  direction={dir_ga}")

    # 裁决表
    print(f"\n=== 裁决表 ({args.held_out}) ===")
    print(f"| arm | n | median |")
    print(f"|-----|---|--------|")
    for arm in args.arms:
        if arm in scores:
            print(f"| {arm:10s} | {len(scores[arm]):2d} | {np.median(scores[arm]):.4f} |")

if __name__ == "__main__":
    main()
