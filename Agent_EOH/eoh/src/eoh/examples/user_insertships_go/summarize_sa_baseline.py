"""汇总 SA 基线网格结果:覆盖率、随机性(重复间 J 方差)、与外部参考表的核对。

用法:
    python summarize_sa_baseline.py --results-dir <含 sa_baseline_summary.csv 的目录> \
        [--archive-ref <参考 JSON,键为 "INST|density|t",值含 SA_J>] \
        [--output <报告 md 路径>]

参考 JSON 仅用于核对复算是否与历史一致,不参与基线本身的计算;不传则只输出覆盖率与随机性。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics


def _load_summary(results_dir: str) -> list[dict]:
    path = os.path.join(results_dir, "sa_baseline_summary.csv")
    if not os.path.exists(path):
        path = os.path.join(results_dir, "sa_baseline_summary_partial.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k in ("t", "J_median", "J_mean", "J_std", "J_min", "J_max",
                      "Res_median", "Res_mean", "Res_std", "composite_median", "composite_mean"):
                r[k] = float(r[k]) if r.get(k) not in (None, "", "None") else None
            for k in ("n_ok", "n_rep"):
                r[k] = int(r[k]) if r.get(k) not in (None, "", "None") else 0
            rows.append(r)
    return rows, path


def _fmt(x, nd=2):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else "NA"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results-dir", required=True)
    p.add_argument("--archive-ref", default="")
    p.add_argument("--output", default="")
    args = p.parse_args()

    rows, src = _load_summary(args.results_dir)
    out_path = args.output or os.path.join(args.results_dir, "sa_baseline_report.md")

    total = len(rows)
    covered = [r for r in rows if r["n_ok"] >= 1]
    full = [r for r in rows if r["n_ok"] == r["n_rep"] and r["n_rep"] > 0]
    failed = [r for r in rows if r["n_ok"] == 0]
    # 随机性:重复间 J 完全一致(std==0)视为确定性
    deterministic = [r for r in covered if r["J_std"] == 0]
    stochastic = [r for r in covered if r["J_std"] and r["J_std"] > 0]

    ref = {}
    if args.archive_ref and os.path.exists(args.archive_ref):
        ref = json.load(open(args.archive_ref, encoding="utf-8"))

    recon = []          # 双方都有,可比
    recovered = []      # 参考缺、本次有
    for r in covered:
        key = f"{r['inst']}|{r['density']}|{r['t']:.1f}"
        rv = ref.get(key)
        saj_ref = rv.get("SA_J") if rv else None
        if saj_ref is None:
            if key in ref:
                recovered.append(r)
            continue
        my = r["J_median"]
        d = my - saj_ref
        pct = (d / saj_ref * 100.0) if saj_ref else None
        recon.append((r, saj_ref, d, pct))

    exact = [x for x in recon if abs(x[2]) < 0.01]
    close = [x for x in recon if 0.01 <= abs(x[2]) and (x[3] is not None and abs(x[3]) < 0.5)]
    differ = [x for x in recon if x not in exact and x not in close]

    L = []
    L.append("# SA 基线网格 · J_SA 汇总与核对\n")
    L.append(f"> 结果来源:`{os.path.basename(src)}`;单元 = RC101–105 × 密度 × 到达缩放 t。\n")
    L.append("## 1. 覆盖率\n")
    L.append("| 项 | 数量 |")
    L.append("|---|---:|")
    L.append(f"| 单元总数 | {total} |")
    L.append(f"| 至少 1 次有效(n_ok≥1) | {len(covered)} |")
    L.append(f"| 全部重复有效(n_ok=n_rep) | {len(full)} |")
    L.append(f"| 完全失败(n_ok=0) | {len(failed)} |")
    if failed:
        L.append("")
        L.append("完全失败单元:" + ", ".join(f"{r['inst']} {r['density']} t{r['t']:.1f}" for r in failed))
    L.append("")
    L.append("## 2. 随机性(重复间 J 方差)\n")
    L.append(f"- 有效单元中 **J 完全确定**(std=0):{len(deterministic)}/{len(covered)}")
    L.append(f"- **J 有波动**(std>0):{len(stochastic)}/{len(covered)}")
    if stochastic:
        L.append("")
        L.append("| 波动单元 | J_median | J_std | J_min | J_max |")
        L.append("|---|---:|---:|---:|---:|")
        for r in sorted(stochastic, key=lambda x: -(x["J_std"] or 0))[:15]:
            L.append(f"| {r['inst']} {r['density']} t{r['t']:.1f} | {_fmt(r['J_median'])} | "
                     f"{_fmt(r['J_std'])} | {_fmt(r['J_min'])} | {_fmt(r['J_max'])} |")
    L.append("")

    if ref:
        L.append("## 3. 与参考表核对\n")
        L.append(f"- 双方均有、可比单元:{len(recon)}")
        L.append(f"  - **完全一致**(|ΔJ|<0.01):{len(exact)}")
        L.append(f"  - 接近(|ΔJ%|<0.5%):{len(close)}")
        L.append(f"  - 有差异:{len(differ)}")
        L.append(f"- **参考缺失、本次复算补齐**:{len(recovered)}")
        if recovered:
            L.append("  - " + ", ".join(f"{r['inst']} {r['density']} t{r['t']:.1f}(J={_fmt(r['J_median'])})"
                                        for r in recovered))
        if differ:
            L.append("")
            L.append("| 有差异单元 | 本次 J_median | 参考 SA_J | ΔJ | ΔJ% |")
            L.append("|---|---:|---:|---:|---:|")
            for r, saj, d, pct in sorted(differ, key=lambda x: -abs(x[2]))[:20]:
                L.append(f"| {r['inst']} {r['density']} t{r['t']:.1f} | {_fmt(r['J_median'])} | "
                         f"{_fmt(saj)} | {_fmt(d)} | {_fmt(pct,1)}% |")
        L.append("")

    # 按密度的 J_SA 概览
    L.append("## 4. 各密度 J_SA 概览(有效单元)\n")
    L.append("| 密度 | 有效单元 | J_median 中位 | Res_median 中位(墙钟秒) |")
    L.append("|---|---:|---:|---:|")
    for dens in ("d25", "d50", "d75"):
        sub = [r for r in covered if r["density"] == dens]
        if not sub:
            continue
        jm = statistics.median([r["J_median"] for r in sub if r["J_median"] is not None])
        rm = statistics.median([r["Res_median"] for r in sub if r["Res_median"] is not None])
        L.append(f"| {dens} | {len(sub)} | {_fmt(jm)} | {_fmt(rm,3)} |")
    L.append("")
    L.append("> 注:Res 为进程墙钟秒,随机器/负载而变(非跨机可比);J 为路由总成本,跨机可复现。")
    L.append("> 复合目标 J+0.2·Res 里 Res 权重小,J 主导;SA 与 EOH 应在同机同配置下比较。\n")

    text = "\n".join(L)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
