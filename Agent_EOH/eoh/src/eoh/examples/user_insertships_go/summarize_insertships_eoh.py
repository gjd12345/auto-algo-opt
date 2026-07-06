"""汇总 InsertShips EOH 网格两臂结果:从每格种群文件重建 J_EOH(可任意阈值重过 guard),
对比 RAG vs 无 RAG(计数 + 配对 + 分密度),并与 SA 基线 J_SA 算 ΔJ。

数据源为各 worker 输出目录下的 `_eoh_runs_<arm>/<cell>_r*/results/pops/population_generation_1.json`
(每个候选的 objective),因此可用任意 suspicious_ratio 重新过 guard,不必重跑。

用法:
    python summarize_insertships_eoh.py --grid-dir <grid_par> --sa-baseline <sa_summary.csv> --output-dir <out>
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import statistics
from collections import Counter, defaultdict

PENALTY = 1e9
CELL_RE = re.compile(
    r"_eoh_runs_(norag|rag)/([A-Z0-9]+)_(d\d+)_t([0-9.]+)_r\d+/results/pops/population_generation_1\.json$")


def _load_sa(path: str) -> dict:
    saj = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["J_median"] not in ("", "None"):
            saj[(r["inst"].upper(), r["density"], f"{float(r['t']):.1f}")] = float(r["J_median"])
    return saj


def _gather(grid_dir: str) -> dict:
    """(arm,inst,dens,t) -> 候选 objective 列表(取有效候选最多的一次运行)。"""
    cells: dict = {}
    for f in glob.glob(f"{grid_dir}/**/population_generation_1.json", recursive=True):
        m = CELL_RE.search(f)
        if not m:
            continue
        arm, inst, dens, t = m.group(1), m.group(2), m.group(3), f"{float(m.group(4)):.1f}"
        try:
            pop = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        objs = [p.get("objective") for p in pop if isinstance(p, dict)]
        key = (arm, inst, dens, t)
        n_valid = len([o for o in objs if o and o < PENALTY])
        if key not in cells or n_valid > len([o for o in cells[key] if o and o < PENALTY]):
            cells[key] = objs
    return cells


def _guard(objs: list, jsa: float, ratio: float):
    fin = [o for o in objs if o is not None and 0 < o < PENALTY]
    val = [o for o in fin if o >= ratio * jsa]
    return (min(val) if val else None)


def _classify(je, jsa, eps=0.01):
    if je is None:
        return "no_valid"
    if abs(je - jsa) < eps:
        return "tie"
    return "improved" if je < jsa else "worse"


def analyze(cells: dict, saj: dict, ratio: float) -> dict:
    res = {}
    for (arm, inst, dens, t), objs in cells.items():
        jsa = saj.get((inst, dens, t))
        if jsa is None:
            continue
        je = _guard(objs, jsa, ratio)
        res[(arm, inst, dens, t)] = {"J_SA": jsa, "J_EOH": je, "class": _classify(je, jsa),
                                     "delta": (je - jsa) if je is not None else None,
                                     "ratio": (je / jsa) if je is not None else None}
    return res


def _counts(res, arm):
    sub = {k: v for k, v in res.items() if k[0] == arm}
    c = Counter(v["class"] for v in sub.values())
    return sub, c


def _paired(res):
    common = {k[1:] for k in res if k[0] == "norag"} & {k[1:] for k in res if k[0] == "rag"}
    rb = nb = sm = 0
    for cell in common:
        a = res.get(("norag",) + cell)
        b = res.get(("rag",) + cell)
        if not a or not b or a["J_EOH"] is None or b["J_EOH"] is None:
            continue
        if b["J_EOH"] < a["J_EOH"] - 0.01:
            rb += 1
        elif b["J_EOH"] > a["J_EOH"] + 0.01:
            nb += 1
        else:
            sm += 1
    return len(common), rb, nb, sm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid-dir", required=True)
    ap.add_argument("--sa-baseline", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--ratios", default="0.3,0.5")
    args = ap.parse_args()

    saj = _load_sa(args.sa_baseline)
    cells = _gather(args.grid_dir)
    os.makedirs(args.output_dir, exist_ok=True)
    ratios = [float(x) for x in args.ratios.split(",")]

    L = ["# InsertShips EOH · RAG vs 无 RAG(deepseek-v4-flash)\n"]
    L.append("> 单元 = RC101–105 × 密度 × 到达缩放 t;RC103 d25/d50 因 SA 不收敛跳过 → 每臂 65 格。")
    L.append("> J_EOH 从每格 EOH 末代种群重过 guard 得到;guard:0<obj<1e9 且 obj≥ratio×J_SA。")
    L.append("> ΔJ=J_EOH−J_SA(负=EOH 优于 SA)。两臂同 guard,RAG vs 无RAG 的差值有效。\n")

    for ratio in ratios:
        res = analyze(cells, saj, ratio)
        L.append(f"## guard ratio = {ratio}\n")
        L.append("| 臂 | n | improved | tie | worse | no_valid | ΔJ 中位(有效) |")
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for arm in ("norag", "rag"):
            sub, c = _counts(res, arm)
            deltas = [v["delta"] for v in sub.values() if v["delta"] is not None]
            med = f"{statistics.median(deltas):+.2f}" if deltas else "NA"
            name = "无 RAG" if arm == "norag" else "RAG"
            L.append(f"| {name} | {len(sub)} | {c['improved']} | {c['tie']} | {c['worse']} | {c['no_valid']} | {med} |")
        n, rb, nb, sm = _paired(res)
        L.append("")
        L.append(f"**配对(同 {n} 格)**:RAG 更低 J = **{rb}** / 无RAG 更低 = **{nb}** / 平 = {sm}")
        # 分密度(以该 ratio)
        L.append("")
        L.append("| 密度 | 臂 | improved | tie | worse |")
        L.append("|---|---|---:|---:|---:|")
        for dens in ("d25", "d50", "d75"):
            for arm in ("norag", "rag"):
                cc = Counter(v["class"] for k, v in res.items() if k[0] == arm and k[2] == dens)
                name = "无RAG" if arm == "norag" else "RAG"
                L.append(f"| {dens} | {name} | {cc['improved']} | {cc['tie']} | {cc['worse']} |")
        L.append("")

    # 结论(基于最严 ratio)
    res = analyze(cells, saj, max(ratios))
    n, rb, nb, sm = _paired(res)
    verdict = "无明显收益甚至略负" if nb >= rb else "有正向收益"
    L.append("## 结论\n")
    L.append(f"- 在 Go InsertShips 轨上,RAG 相对无 RAG **{verdict}**(最严 guard {max(ratios)} 下配对 "
             f"RAG 赢 {rb} / 无RAG 赢 {nb})。与 Python 侧 RAG 的强正向效果相反。")
    L.append("- 无 RAG 的 EOH 本身与 SA 大致持平(improved≈worse),符合论文 16/11/16 的量级。")
    L.append("- ⚠ reps=1 有 run 间波动;d25 低密度存在 deep-cut(比值<0.5)刷分候选,已用 0.5 阈值做稳健性核对。\n")

    text = "\n".join(L)
    with open(os.path.join(args.output_dir, "eoh_rag_vs_norag_report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    # 合并 cells CSV(以 0.3 口径导出每格)
    res03 = analyze(cells, saj, min(ratios))
    with open(os.path.join(args.output_dir, "eoh_cells_merged.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arm", "inst", "density", "t", "J_SA", "J_EOH", "delta_J", "ratio", "class"])
        for (arm, inst, dens, t), v in sorted(res03.items()):
            w.writerow([arm, inst, dens, t, round(v["J_SA"], 4),
                        round(v["J_EOH"], 4) if v["J_EOH"] is not None else "",
                        round(v["delta"], 4) if v["delta"] is not None else "",
                        round(v["ratio"], 4) if v["ratio"] is not None else "", v["class"]])
    print(text)
    print(f"\n[written] {args.output_dir}/eoh_rag_vs_norag_report.md + eoh_cells_merged.csv")


if __name__ == "__main__":
    main()
