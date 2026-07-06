"""InsertShips EOH 网格:每格跑一轮 EOH 进化(gen=1, pop=4,种子=贪心 InsertShips),取 guard 过滤后的最优
候选作为 J_EOH,与 SA 基线 J_SA 比,算 ΔJ 与 improved/tie/worse。

两臂:
  --rag     注入 RAG 上下文(insertships_v1.txt)→ 我们的方法
  (默认无)  不注入 → 论文式无 RAG 基线

单元 = RC101–105 × 密度 × 到达缩放 t;RC103 d25/d50 因 SA 不收敛(无 J_SA 锚点)自动跳过。
guard(沿用清洗规则):候选 objective 有效需 0<obj<1e9 且 obj>=suspicious_ratio×J_SA;
低于该线视为"刷分"(丢单/把费用设小)候选,剔除。J_EOH = 有效候选最小值。

用法(在本目录下运行,先 export API env):
    python run_insertships_eoh_grid.py --output-dir <dir> --sa-baseline <sa_summary.csv> [--rag]
        [--densities d25,d50,d75] [--scales 1.0,0.9,0.8,0.7,0.6] [--repeats 1] [--gens 1] [--pop 4]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # Agent_EOH/eoh/src(含 eoh 包)
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

SUSPICIOUS_RATIO = 0.3
PENALTY = 1e9


def _load_sa_baseline(path: str) -> dict:
    """读取 SA 基线 summary.csv → {(INST,density,t): J_SA(中位)}。"""
    saj = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            jm = r.get("J_median")
            if jm in (None, "", "None"):
                continue
            key = (r["inst"].upper(), r["density"], f"{float(r['t']):.1f}")
            saj[key] = float(jm)
    return saj


def _read_population(out_dir: str, gen: int) -> list[dict]:
    f = os.path.join(out_dir, "results", "pops", f"population_generation_{gen}.json")
    if not os.path.exists(f):
        return []
    pop = json.load(open(f, encoding="utf-8"))
    return [p for p in pop if isinstance(p, dict)]


def _guard(objectives: list[float], j_sa: float) -> dict:
    """返回 raw_best(最小有效非惩罚)、guarded_best(排除可疑低)。"""
    finite = [o for o in objectives if o is not None and 0 < o < PENALTY]
    raw_best = min(finite) if finite else None
    valid = [o for o in finite if o >= SUSPICIOUS_RATIO * j_sa]
    guarded_best = min(valid) if valid else None
    suspicious = [o for o in finite if o < SUSPICIOUS_RATIO * j_sa]
    return {"raw_best": raw_best, "guarded_best": guarded_best,
            "n_finite": len(finite), "n_suspicious": len(suspicious)}


def _run_one_eoh(ev, seed_path: str, endpoint: str, key: str, model: str,
                 gens: int, pop: int, out_dir: str, nproc: int = 4) -> list[float]:
    """跑一轮 EOH,返回末代种群的 objective 列表。"""
    from eoh import EVOL
    from eoh.utils.getParas import Paras
    paras = Paras()
    paras.exp_output_path = out_dir
    paras.set_paras(
        method="eoh", problem=ev,
        llm_api_endpoint=endpoint, llm_api_key=key, llm_model=model,
        ec_pop_size=pop, ec_n_pop=gens, ec_operators=["m1", "m2"],
        exp_n_proc=nproc, exp_use_seed=True, exp_seed_path=seed_path,
        eva_timeout=120, eva_numba_decorator=False,
    )
    EVOL(paras).run()
    pop_rows = _read_population(out_dir, gens)
    return [p.get("objective") for p in pop_rows]


def run_grid(args: argparse.Namespace) -> None:
    import prob_insertships_go

    saj = _load_sa_baseline(args.sa_baseline)
    arm = "rag" if args.rag else "norag"

    if args.rag:
        ctx = open(args.rag_context, encoding="utf-8").read().strip()
        os.environ["EOH_RAG_CONTEXT"] = ctx
        print(f"[arm=rag] RAG context chars={len(ctx)} from {os.path.basename(args.rag_context)}", flush=True)
    else:
        os.environ.pop("EOH_RAG_CONTEXT", None)
        print("[arm=norag] no RAG context", flush=True)
    os.environ.setdefault("EOH_TARGET_FUNCTION", "InsertShips")

    endpoint = os.environ["DEEPSEEK_API_ENDPOINT"]
    key = os.environ["DEEPSEEK_API_KEY"]
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    seed_path = os.path.join(HERE, args.seed_file)
    print(f"[cfg] endpoint={endpoint} model={model} seed={os.path.basename(seed_path)}", flush=True)

    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    eoh_runs = os.path.join(out_dir, f"_eoh_runs_{arm}")

    densities = [d.strip() for d in args.densities.split(",") if d.strip()]
    scales = [float(s) for s in args.scales.split(",") if s.strip()]

    rows = []
    only = set(args.only_cells.split(",")) if args.only_cells else None
    t_start = time.time()
    idx = 0

    for density in densities:
        for scale in scales:
            ev0 = prob_insertships_go.Evaluation(
                sim_time_multi=args.sim_time_multi, max_instances=args.instances,
                dataset_density=density, use_density_source_dirs=True,
                arrival_scale=scale, sim_time_interval=1, run_timeout_s=args.run_timeout_s,
            )
            for inst_path in ev0.instance_files:
                inst = os.path.basename(inst_path).replace(".json", "").upper()
                cell = f"{inst}|{density}|{scale:.1f}"
                if only and cell not in only:
                    continue
                j_sa = saj.get((inst, density, f"{scale:.1f}"))
                if j_sa is None:
                    print(f"[skip] {cell} 无 J_SA 锚点(SA 病态/缺失),跳过", flush=True)
                    continue
                idx += 1

                best_over_reps = None
                raw_over_reps = None
                susp_total = 0
                for rep in range(args.repeats):
                    ev = prob_insertships_go.Evaluation(
                        sim_time_multi=args.sim_time_multi, max_instances=args.instances,
                        dataset_density=density, use_density_source_dirs=True,
                        arrival_scale=scale, sim_time_interval=1, run_timeout_s=args.run_timeout_s,
                    )
                    ev.instance_files = [inst_path]
                    cell_out = os.path.join(eoh_runs, f"{inst}_{density}_t{scale:.1f}_r{rep}")
                    shutil.rmtree(cell_out, ignore_errors=True)
                    os.makedirs(cell_out, exist_ok=True)
                    try:
                        objs = _run_one_eoh(ev, seed_path, endpoint, key, model, args.gens, args.pop, cell_out, args.eoh_nproc)
                    except (Exception, SystemExit) as e:
                        # EOH 在 API 自检失败时会 sys.exit(SystemExit 不是 Exception 子类),
                        # 单格失败不应打断整个 worker,记为本格无效、继续下一格。
                        print(f"  [warn] {cell} rep{rep} EOH 异常: {type(e).__name__} {e}", flush=True)
                        objs = []
                    g = _guard(objs, j_sa)
                    susp_total += g["n_suspicious"]
                    if g["guarded_best"] is not None:
                        if best_over_reps is None or g["guarded_best"] < best_over_reps:
                            best_over_reps = g["guarded_best"]
                    if g["raw_best"] is not None:
                        if raw_over_reps is None or g["raw_best"] < raw_over_reps:
                            raw_over_reps = g["raw_best"]

                j_eoh = best_over_reps
                delta = (j_eoh - j_sa) if j_eoh is not None else None
                if j_eoh is None:
                    cls = "no_valid_eoh"
                elif abs(delta) < args.tie_eps:
                    cls = "tie"
                elif delta < 0:
                    cls = "improved"
                else:
                    cls = "worse"
                rows.append({
                    "inst": inst, "density": density, "t": scale, "arm": arm,
                    "J_SA": round(j_sa, 4),
                    "J_EOH": round(j_eoh, 4) if j_eoh is not None else None,
                    "raw_best": round(raw_over_reps, 4) if raw_over_reps is not None else None,
                    "delta_J": round(delta, 4) if delta is not None else None,
                    "class": cls, "n_suspicious": susp_total, "repeats": args.repeats,
                })
                el = time.time() - t_start
                de = f"{delta:+.2f}" if delta is not None else "NA"
                print(f"[{idx}] {cell} J_SA={j_sa:.2f} J_EOH={j_eoh if j_eoh is None else round(j_eoh,2)} "
                      f"ΔJ={de} {cls} susp={susp_total} ({el:.0f}s)", flush=True)
                _dump(out_dir, arm, args, rows, partial=True)

    _dump(out_dir, arm, args, rows, partial=False)
    # 汇总计数
    from collections import Counter
    c = Counter(r["class"] for r in rows)
    print(f"\n=== arm={arm} 完成 {len(rows)} 格,用时 {time.time()-t_start:.0f}s ===", flush=True)
    print(f"improved={c['improved']} tie={c['tie']} worse={c['worse']} "
          f"no_valid_eoh={c['no_valid_eoh']}", flush=True)


def _dump(out_dir, arm, args, rows, partial: bool):
    suffix = "_partial" if partial else ""
    payload = {
        "arm": arm,
        "config": {"gens": args.gens, "pop": args.pop, "repeats": args.repeats,
                   "sim_time_multi": args.sim_time_multi, "run_timeout_s": args.run_timeout_s,
                   "suspicious_ratio": SUSPICIOUS_RATIO, "seed_file": args.seed_file},
        "rows": rows,
    }
    with open(os.path.join(out_dir, f"eoh_{arm}_results{suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, f"eoh_{arm}_cells{suffix}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["inst", "density", "t", "arm", "J_SA", "J_EOH",
                                          "raw_best", "delta_J", "class", "n_suspicious", "repeats"])
        w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description="EOH-Go 网格:每格 J_EOH 与 ΔJ(相对 SA 基线)。")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--sa-baseline", required=True, help="SA 基线 summary.csv 路径(取 J_median)")
    p.add_argument("--rag", action="store_true", help="注入 RAG 上下文;不加则为无 RAG 基线臂")
    p.add_argument("--rag-context", default=os.path.join(
        HERE, "..", "..", "..", "..", "..", "..", "eoh_rag_workspace", "rag", "manual_contexts", "insertships_v1.txt"))
    p.add_argument("--seed-file", default="seeds_insertships_go.json")
    p.add_argument("--densities", default="d25,d50,d75")
    p.add_argument("--scales", default="1.0,0.9,0.8,0.7,0.6")
    p.add_argument("--only-cells", default="", help="逗号分隔如 RC101|d75|1.0,RC104|d50|0.8(pilot 用)")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--gens", type=int, default=1)
    p.add_argument("--pop", type=int, default=4)
    p.add_argument("--instances", type=int, default=5)
    p.add_argument("--eoh-nproc", type=int, default=4, help="单轮 EOH 内部并发评测数(并发多 worker 时调小以限总 API 并发)")
    p.add_argument("--sim-time-multi", type=int, default=10)
    p.add_argument("--run-timeout-s", type=int, default=60)
    p.add_argument("--tie-eps", type=float, default=0.01)
    args = p.parse_args()
    run_grid(args)


if __name__ == "__main__":
    main()
