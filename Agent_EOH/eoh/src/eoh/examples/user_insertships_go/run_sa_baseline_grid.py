"""SA 基线网格:在 Solomon RC 数据集上跑派船调度求解器的模拟退火种子解,得到每个单元的 J_SA。

单元定义(与论文一致):RC101–105 × 密度 d{25,50,75} × 到达时间缩放 t∈{1.0,0.9,0.8,0.7,0.6},共 75 格。
每格:把 SA 种子 InsertShips 注入 go_solver/main.go、编译一次得到 mainbin_sa,再对该格施加 arrival_scale
后的实例串行运行 sim_time_multi 次模拟,解析 J(final cost)与 Res(RES 墙钟秒),复合目标 = J + 0.2·Res。
串行运行保证 Res 不受并发抢占干扰;每格重复 REPEATS 次以刻画随机性(求解器带随机移动)。

用法(在本目录下运行,默认即论文网格):
    python run_sa_baseline_grid.py --output-dir <dir> [--repeats 5] [--densities d25,d50,d75]
        [--scales 1.0,0.9,0.8,0.7,0.6] [--sim-time-multi 10] [--run-timeout-s 90] [--instances 5]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

# 复用主评测器的构建/运行/解析辅助,保证与候选评测口径完全一致(不依赖任何外部实验包)。
from prob_insertships_go import (
    Evaluation,
    _parse_final_cost,
    _parse_res_time,
    _replace_target_method,
    _run_command,
)

RES_WEIGHT = 0.2  # 复合目标里 Res 的权重,与论文一致
FUNC_NAME = "InsertShips"


def _load_sa_seed_code(example_dir: str) -> str:
    """读取 SA 种子的 InsertShips 源码(即项目根 main.go 抽取出的原始实现)。"""
    seed_path = os.path.join(example_dir, "seeds_insertships_go_sa.json")
    with open(seed_path, "r", encoding="utf-8") as f:
        seed = json.load(f)
    code = seed[0]["code"]
    if "func InsertShips" not in code:
        raise ValueError("SA 种子里找不到 InsertShips 定义")
    return code


def _build_sa_binary(ev: Evaluation, sa_code: str, build_dir: str) -> str:
    """把 SA 种子注入 main.go 并编译一次,返回可执行文件路径。"""
    os.makedirs(build_dir, exist_ok=True)
    shutil.copy2(ev.go_main, os.path.join(build_dir, "main.go"))
    shutil.copy2(ev.go_routing, os.path.join(build_dir, "routing.go"))
    shutil.copy2(ev.go_mod, os.path.join(build_dir, "go.mod"))
    if os.path.exists(ev.go_sum):
        shutil.copy2(ev.go_sum, os.path.join(build_dir, "go.sum"))

    _replace_target_method(os.path.join(build_dir, "main.go"), sa_code, FUNC_NAME)

    bin_name = "mainbin_sa.exe"
    build = _run_command(["go", "build", "-o", bin_name, "."], cwd=build_dir, timeout_s=120)
    if build["returncode"] != 0:
        raise RuntimeError(
            f"go build 失败 rc={build['returncode']} timeout={build['timeout']}\n"
            f"stdout={build['stdout']}\nstderr={build['stderr']}"
        )
    return os.path.join(build_dir, bin_name)


def _run_once(binary: str, instance_path: str, sim_time_multi: int, cwd: str, timeout_s: int) -> dict:
    """跑一次求解器,解析 J 与 Res。"""
    run = _run_command([binary, instance_path, str(sim_time_multi)], cwd=cwd, timeout_s=timeout_s)
    out = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
    j = _parse_final_cost(out)
    res = _parse_res_time(out)
    ok = (run["returncode"] == 0) and (j is not None) and (j >= 0) and (not run["timeout"])
    return {
        "J": j,
        "Res": res,
        "composite": (j + RES_WEIGHT * res) if (ok and res is not None) else None,
        "return_code": run["returncode"],
        "timeout": run["timeout"],
        "ok": ok,
        "stderr_tail": (run["stderr"] or "")[-300:],
    }


def _agg(values: list[float]) -> dict:
    """对一格的多次重复做聚合统计。"""
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "std": None, "median": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "mean": statistics.fmean(vals),
        "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
        "median": statistics.median(vals),
        "min": min(vals),
        "max": max(vals),
    }


def run_grid(args: argparse.Namespace) -> dict:
    example_dir = os.path.dirname(os.path.abspath(__file__))
    sa_code = _load_sa_seed_code(example_dir)

    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    build_dir = os.path.join(out_dir, "_build_sa")
    inst_dir = os.path.join(out_dir, "_instances")
    os.makedirs(inst_dir, exist_ok=True)

    densities = [d.strip() for d in args.densities.split(",") if d.strip()]
    scales = [float(s) for s in args.scales.split(",") if s.strip()]

    # 用任意密度构造一个 Evaluation 拿到 go_solver 路径,编译一次 SA 二进制。
    probe = Evaluation(
        sim_time_multi=args.sim_time_multi,
        max_instances=args.instances,
        dataset_density=densities[0],
        use_density_source_dirs=True,
    )
    print(f"[build] go_solver 根目录: {probe.archive_dir}", flush=True)
    binary = _build_sa_binary(probe, sa_code, build_dir)
    print(f"[build] SA 二进制就绪: {binary}", flush=True)

    cell_rows: list[dict] = []   # 每次重复一行
    summary_rows: list[dict] = []  # 每格一行(聚合)

    total_cells = len(densities) * len(scales) * args.instances
    done_cells = 0
    t_start = time.time()

    for density in densities:
        for scale in scales:
            ev = Evaluation(
                sim_time_multi=args.sim_time_multi,
                max_instances=args.instances,
                dataset_density=density,
                use_density_source_dirs=True,
                arrival_scale=scale,
                sim_time_interval=1,
            )
            for inst_path in ev.instance_files:
                inst_name = os.path.basename(inst_path).replace(".json", "").upper()
                # 施加 arrival_scale(密度已在源目录里烘焙,不再过滤 ori/des)。
                filtered = ev._prepare_filtered_json(inst_path, inst_dir)

                j_list, res_list, comp_list = [], [], []
                n_ok = 0
                timed_out = False
                for rep in range(args.repeats):
                    r = _run_once(binary, filtered, args.sim_time_multi, cwd=build_dir, timeout_s=args.run_timeout_s)
                    cell_rows.append({
                        "inst": inst_name, "density": density, "t": scale, "rep": rep,
                        "J": r["J"], "Res": r["Res"], "composite": r["composite"],
                        "return_code": r["return_code"], "timeout": r["timeout"], "ok": r["ok"],
                    })
                    if r["ok"]:
                        n_ok += 1
                        j_list.append(r["J"])
                        res_list.append(r["Res"])
                        if r["composite"] is not None:
                            comp_list.append(r["composite"])
                    else:
                        print(f"  [warn] {inst_name} {density} t{scale} rep{rep} 失败 "
                              f"rc={r['return_code']} timeout={r['timeout']} err={r['stderr_tail'][:120]}", flush=True)
                        # 超时说明该单元病态(求解器不收敛),再重复只是白等满超时,直接判定并跳过其余重复。
                        if r["timeout"]:
                            timed_out = True
                            print(f"  [skip] {inst_name} {density} t{scale} 超时 → 该单元判为超时,跳过剩余重复", flush=True)
                            break

                j_agg = _agg(j_list)
                res_agg = _agg(res_list)
                comp_agg = _agg(comp_list)
                summary_rows.append({
                    "inst": inst_name, "density": density, "t": scale,
                    "n_ok": n_ok, "n_rep": args.repeats, "timed_out": timed_out,
                    "J_median": j_agg["median"], "J_mean": j_agg["mean"], "J_std": j_agg["std"],
                    "J_min": j_agg["min"], "J_max": j_agg["max"],
                    "Res_median": res_agg["median"], "Res_mean": res_agg["mean"], "Res_std": res_agg["std"],
                    "composite_median": comp_agg["median"], "composite_mean": comp_agg["mean"],
                })
                done_cells += 1
                jm = j_agg["median"]
                rm = res_agg["median"]
                jm_s = f"{jm:.2f}" if jm is not None else "NA"
                rm_s = f"{rm:.3f}" if rm is not None else "NA"
                elapsed = time.time() - t_start
                print(f"[{done_cells}/{total_cells}] {inst_name} {density} t{scale} "
                      f"J_med={jm_s} Res_med={rm_s} n_ok={n_ok}/{args.repeats} "
                      f"({elapsed:.0f}s)", flush=True)

                # 增量落盘,防止长跑中断丢结果。
                _dump(out_dir, args, densities, scales, cell_rows, summary_rows, partial=True)

    payload = _dump(out_dir, args, densities, scales, cell_rows, summary_rows, partial=False)
    print(f"\n完成:{done_cells} 格,用时 {time.time()-t_start:.0f}s,结果在 {out_dir}", flush=True)
    return payload


def _dump(out_dir, args, densities, scales, cell_rows, summary_rows, partial: bool) -> dict:
    payload = {
        "config": {
            "densities": densities, "scales": scales, "repeats": args.repeats,
            "sim_time_multi": args.sim_time_multi, "run_timeout_s": args.run_timeout_s,
            "instances": args.instances, "res_weight": RES_WEIGHT, "func_name": FUNC_NAME,
        },
        "cells": cell_rows,
        "summary": summary_rows,
    }
    suffix = "_partial" if partial else ""
    with open(os.path.join(out_dir, f"sa_baseline_results{suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, f"sa_baseline_cells{suffix}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["inst", "density", "t", "rep", "J", "Res", "composite",
                                          "return_code", "timeout", "ok"])
        w.writeheader()
        w.writerows(cell_rows)

    with open(os.path.join(out_dir, f"sa_baseline_summary{suffix}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["inst", "density", "t", "n_ok", "n_rep", "timed_out",
                                          "J_median", "J_mean", "J_std", "J_min", "J_max",
                                          "Res_median", "Res_mean", "Res_std",
                                          "composite_median", "composite_mean"])
        w.writeheader()
        w.writerows(summary_rows)
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="Solomon RC 上派船调度 SA 基线网格,产出每格 J_SA。")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--densities", default="d25,d50,d75")
    p.add_argument("--scales", default="1.0,0.9,0.8,0.7,0.6")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--sim-time-multi", type=int, default=10)
    p.add_argument("--run-timeout-s", type=int, default=90)
    p.add_argument("--instances", type=int, default=5)
    args = p.parse_args()
    run_grid(args)


if __name__ == "__main__":
    main()
