"""
模块：批量实验运行器（batch_runner）
功能：读取一份 JSON 实验清单（manifest），校验其合法性，展开成一组待跑实验，
      再逐个调用 EOH 单次运行命令行（eoh_single_runner）真正执行。
职责：
    - 解析并校验 manifest（必填字段、实验臂类型、问题类型、代数取值等）；
    - 把「问题 × 实验臂 × 代数 × 重复次数」笛卡尔展开成实验矩阵，并做安全上限检查；
    - 为每个实验拼装子进程命令，串联跨进程共享池（岛屿模型：取更优种子、回写成功结果）；
    - 记录每次运行的状态/耗时/最优目标值，最终写出运行索引 run_index.json。
接口：
    - main() -> None：命令行入口，解析参数并驱动整个批量流程。
    - shared_pool_register / shared_pool_best / shared_pool_register_code / shared_pool_best_codes：
      围绕 PoolAPI 的便捷封装函数。
    - _validate_manifest / _matrix_count / _build_cmd 等：内部辅助函数。
输入：
    - --manifest：实验清单 JSON 路径（必填）；
    - 环境变量 EOH_OFFICIAL_PYTHON / EOH_OFFICIAL_ROOT：默认 Python 解释器与官方根目录；
    - 可选 --shared-pool-dir：跨进程共享池目录，用于岛屿模型的种群共享。
输出：
    - 每个实验一个输出子目录（含 official_eoh_run_summary.json）；
    - 汇总运行索引 run_index.json。
示例：
    python -m eoh_rag.experiments.batch_runner --manifest my_manifest.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Shared Pool 便捷函数
# ---------------------------------------------------------------------------
# 所有跨进程共享池的读写统一由 PoolAPI 承担。
# 下面 4 个 shared_pool_* 函数是围绕 PoolAPI 的轻量便捷封装，各自转发一行调用。
# 内部代码可直接 import PoolAPI。
# ---------------------------------------------------------------------------

from eoh_rag.experiments.pool_api import PoolAPI

logger = logging.getLogger(__name__)


def shared_pool_register(pool_dir: Path, problem: str, run_dir: str, objective: float) -> None:
    """便捷封装：转发到 PoolAPI(pool_dir).register_run(...)。"""
    PoolAPI(pool_dir).register_run(problem, run_dir, objective)


def shared_pool_best(pool_dir: Path, problem: str) -> str:
    """便捷封装：转发到 PoolAPI(pool_dir).best_run(problem)。"""
    return PoolAPI(pool_dir).best_run(problem)


def shared_pool_register_code(pool_dir: Path, problem: str, code: str, objective: float) -> None:
    """便捷封装：转发到 PoolAPI(pool_dir).register_code(...)。"""
    PoolAPI(pool_dir).register_code(problem, code, objective)


def shared_pool_best_codes(pool_dir: Path, problem: str, top_k: int = 3) -> list[dict]:
    """便捷封装：转发到 PoolAPI(pool_dir).best_codes(problem, top_k)。"""
    return PoolAPI(pool_dir).best_codes(problem, top_k=top_k)


# ---------------------------------------------------------------------------
# Online Outcome: append outcome records after each successful run
# ---------------------------------------------------------------------------

# Problem baselines for card synthesis threshold —— 统一走 baselines.py
from eoh_rag.experiments.baselines import PROBLEM_BASELINES as _PROBLEM_BASELINES
from eoh_rag.utils.file_lock import exclusive_lock


def _maybe_synthesize_card(pool_dir: str, problem: str, code: str, objective: float) -> None:
    """当本次目标值相对基线提升超过 5% 时，自动把它合成为一张算法卡片并写入语料库。

    参数：
        pool_dir：共享池目录（此处仅为签名占位，实际写入的是固定语料库路径）。
        problem：问题类型标识（如 bp_online）。
        code：本次跑出的启发式代码文本。
        objective：本次的最优目标值（越小越好）。
    行为：
        - 基线来自 baselines.py；若该问题没有基线则直接返回；
        - 提升幅度不足 5% 时不合成；
        - 卡片 id 已存在则跳过；写入时用 flock 文件锁避免多进程并发写坏文件；
        - 任何异常都被捕获并打印告警，不影响主流程。
    """
    baseline = _PROBLEM_BASELINES.get(problem)
    if baseline is None:
        return
    # 提升幅度 =（基线 - 本次）/ |基线|，目标值越小越好，故为正表示更优
    improvement = (baseline - objective) / abs(baseline)
    if improvement < 0.05:
        return
    try:
        from eoh_rag.rag.card_synthesis import synthesize_card
        from eoh_rag.rag.schemas import load_corpus, save_corpus
        corpus_path = Path("eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl")
        card = synthesize_card(problem, code, run_info={"objective": objective})
        existing = load_corpus(corpus_path)
        # 去重：同 id 卡片已存在则不再追加
        if any(c.id == card.id for c in existing):
            return
        existing.append(card)
        # 追加写 JSONL，flock 独占锁保证跨进程写入原子性
        with open(corpus_path, "a", encoding="utf-8") as f:
            with exclusive_lock(f):
                f.write(json.dumps(card.__dict__, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("card_synthesis failed")


def _append_online_outcome(summary_path: Path, problem: str, outcome_file: str) -> None:
    """从一次运行的 summary 中抽取 RAG 注入的效果记录，并追加写入 outcome 文件。

    参数：
        summary_path：单次运行产出的 official_eoh_run_summary.json 路径。
        problem：问题类型标识。
        outcome_file：outcome 记录累积文件路径；为空则不写。
    行为：
        - 读取 summary 中的 rag_trace 与 run_summary；
        - 若本次没有注入任何 RAG 条目（rag_injected_items 为空）则直接返回；
        - 组装注入审计与本次生成结果，构造 outcome 记录并追加保存；
        - 任何异常都被捕获并打印告警，不影响主流程。
    """
    from eoh_rag.rag.card_outcomes import build_outcome_records, save_outcomes
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        rag_trace = data.get("rag_trace") or {}
        run_summary = data.get("run_summary") or {}
        injected = rag_trace.get("rag_injected_items", [])
        if not injected:
            return
        injection_audit = {
            "rag_injected_items": injected,
            "rag_omitted_items": rag_trace.get("rag_omitted_items", []),
        }
        gen_result = {
            "population_size": run_summary.get("population_size", 4),
            "valid_candidates": run_summary.get("valid_candidates", 0),
            "best_objective": run_summary.get("best_objective"),
            # 以问题的官方基线作为纯基线：build_outcome_records 据此算 delta_pct 与
            # objective_success，让 RAG 注入的在线效果反馈形成闭环（best 优于基线记为成功）。
            "pure_baseline": _PROBLEM_BASELINES.get(problem),
        }
        records = build_outcome_records(
            run_id=summary_path.parent.name,
            problem=problem,
            generation=run_summary.get("latest_generation", 4),
            injection_audit=injection_audit,
            generation_result=gen_result,
        )
        if records and outcome_file:
            save_outcomes(records, Path(outcome_file), append=True)
    except Exception:
        logger.exception("online_outcome_update failed")

# 直接复用现成的 EOH 单次运行命令行模块，批量运行器只负责调度与拼参数
RUNNER_MODULE = "eoh_rag.experiments.eoh_single_runner"

# 默认 Python 解释器与官方根目录，均可由环境变量覆盖，manifest 中的同名字段优先级更高
_DEFAULT_PYTHON = os.environ.get("EOH_OFFICIAL_PYTHON", "")
# 官方 EoH 默认指向仓内 vendored 副本 official_eoh/（可由环境变量或 manifest 覆盖）
_DEFAULT_ROOT = os.environ.get("EOH_OFFICIAL_ROOT", "") or str(Path(__file__).resolve().parents[2] / "official_eoh")
# 合法的实验臂集合：纯 EOH、仅 API、文献 RAG、历史 RAG、混合 RAG、上下文文件
VALID_ARMS = {"pure_eoh", "api_only", "literature_rag", "history_rag", "mixed_rag", "context_file"}


def _arm_card_ids(arm: dict[str, Any]) -> tuple[list[str], str]:
    """从一个实验臂配置中解析出候选卡片 id 列表及其来源字段名。

    按 candidate_card_ids → selected_card_ids → cards 的优先级依次查找，
    返回（卡片 id 列表, 来源字段名）；都没有时返回（空列表, "none"）。
    """
    if arm.get("candidate_card_ids"):
        return list(arm.get("candidate_card_ids", [])), "candidate_card_ids"
    if arm.get("selected_card_ids"):
        return list(arm.get("selected_card_ids", [])), "selected_card_ids"
    if arm.get("cards"):
        return list(arm.get("cards", [])), "cards"
    return [], "none"


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """校验 manifest 的合法性，返回错误信息列表（为空表示全部通过）。

    检查项：
        - 必填顶层键 suite / problems / arms 是否齐全；
        - arms 是非空列表，且每个臂的 runner_arm 在 VALID_ARMS 内；
        - 使用 tocc_* 上下文策略的臂必须提供候选卡片 id；
        - problems 只允许已支持的问题类型；
        - generations 若存在，必须是非负整数列表。
    """
    errors: list[str] = []
    required = ["suite", "problems", "arms"]
    for key in required:
        if key not in manifest:
            errors.append(f"missing required key: {key}")

    arms = manifest.get("arms", [])
    if not isinstance(arms, list) or len(arms) == 0:
        errors.append("arms must be a non-empty list")
    for i, arm in enumerate(arms):
        runner = arm.get("runner_arm", "")
        if runner not in VALID_ARMS:
            errors.append(f"arm[{i}] invalid runner_arm: {runner!r}, must be one of {sorted(VALID_ARMS)}")
        strategy = arm.get("context_strategy", "")
        card_ids, _ = _arm_card_ids(arm)
        # tocc_* 策略依赖具体卡片作为上下文，缺少卡片即报错
        if strategy.startswith("tocc_") and not card_ids:
            errors.append(
                f"arm[{i}] tocc_* strategy requires candidate_card_ids, selected_card_ids, or cards"
            )

    problems = manifest.get("problems", [])
    for p in problems:
        if p not in ("bp_online", "tsp_construct", "cvrp_construct"):
            errors.append(f"unknown problem: {p!r}")

    gens = manifest.get("generations", [])
    if isinstance(gens, list) and any(not isinstance(g, int) or g < 0 for g in gens):
        errors.append("generations must be a list of non-negative ints")

    return errors


def _matrix_count(manifest: dict[str, Any]) -> int:
    """按「问题数 × 实验臂数 × 代数取值数 × 重复次数」计算展开后的总运行数。"""
    return (
        len(manifest.get("problems", []))
        * len(manifest.get("arms", []))
        * len(manifest.get("generations", [1]))
        * manifest.get("repeats", 1)
    )


def _build_cmd(
    manifest: dict[str, Any],
    problem: str,
    arm: dict[str, Any],
    generation: int,
    repeat: int,
    output_dir: str,
    prev_run_dir: str = "",
    seed_codes_path: str = "",
) -> list[str]:
    """为「某问题 × 某实验臂 × 某代数」拼装调用单次运行器的完整命令行参数列表。

    参数：
        manifest：整份实验清单，用于取全局默认（pop_size、operators、超时等）。
        problem / arm / generation / repeat：本次实验在矩阵中的坐标。
        output_dir：本次运行的输出目录。
        prev_run_dir：上一次运行目录，用于历史链式 RAG 传递种子。
        seed_codes_path：从共享池导出的种子代码文件路径（岛屿模型用）。
    返回：可直接交给 subprocess.run 的命令行字符串列表。

    说明：仅对 RAG 类实验臂（literature/history/mixed）追加 RAG 相关参数；
    manifest 与 arm 各自的 rag 配置会合并，arm 级别覆盖 manifest 级别。
    """
    cmd = [
        manifest.get("python_exe") or _DEFAULT_PYTHON or sys.executable,
        "-m",
        RUNNER_MODULE,
        "--problem", problem,
        "--arm", arm["runner_arm"],
        "--pop-size", str(manifest.get("pop_size", 4)),
        "--generations", str(generation),
        "--operators", manifest.get("operators", "i1"),
        "--n-processes", "1",
        "--eval-timeout-s", "40",
        "--llm-timeout-s", "180",
        "--run-timeout-s", str(manifest.get("run_timeout_s", 1800)),
        "--output-dir", output_dir,
        "--official-root", manifest.get("official_root") or _DEFAULT_ROOT,
        "--python", manifest.get("python_exe") or _DEFAULT_PYTHON or sys.executable,
    ]
    # 合并 RAG 配置：arm 级别覆盖 manifest 级别
    rag = {**manifest.get("rag", {}), **arm.get("rag", {})}
    if arm["runner_arm"] in ("literature_rag", "history_rag", "mixed_rag"):
        cmd.extend(["--rag-top-k", str(rag.get("top_k", 2))])
        cmd.extend(["--rag-max-chars", str(rag.get("max_chars", 2500))])
        if arm.get("rag_query"):
            cmd.extend(["--rag-query", arm["rag_query"]])
        card_ids, card_source = _arm_card_ids(arm)
        if card_ids:
            cmd.extend(["--selected-card-ids", ",".join(card_ids)])
            cmd.extend(["--candidate-card-source", card_source])
        # 是否启用「上一次运行目录」链式传递：启用时优先用运行时传入的 prev_run_dir
        if rag.get("use_prev_run_dir_chain"):
            effective_prev = prev_run_dir or rag.get("prev_run_dir", "")
        else:
            effective_prev = rag.get("prev_run_dir", "")
        if effective_prev:
            cmd.extend(["--prev-run-dir", effective_prev])
        if rag.get("outcome_file"):
            cmd.extend(["--outcome-file", str(rag["outcome_file"])])
        if rag.get("rerank_mode"):
            cmd.extend(["--rag-rerank", rag["rerank_mode"]])
        if rag.get("rerank_temperature"):
            cmd.extend(["--rag-rerank-temperature", str(rag["rerank_temperature"])])
        # top_fraction 为 1.0 表示不裁剪，无需传参
        if rag.get("top_fraction") and rag["top_fraction"] != 1.0:
            cmd.extend(["--rag-top-fraction", str(rag["top_fraction"])])
    # 自适应早停:manifest 顶层 adaptive_stop.enabled 为真时透传给 runner
    astop = manifest.get("adaptive_stop") or {}
    if astop.get("enabled"):
        cmd.extend([
            "--adaptive-stop",
            "--stop-window", str(astop.get("window", 5)),
            "--stop-min-gap", str(astop.get("min_gap", 0.0)),
        ])
    if seed_codes_path:
        cmd.extend(["--seed-codes", seed_codes_path])
    # manifest 顶层声明的模型透传给 runner,使实验声明与实际调用一致;留空则由 runner 端环境变量决定。
    model = manifest.get("model")
    if model:
        cmd.extend(["--llm-model", str(model)])
    return cmd


def main() -> None:
    """命令行入口：解析参数、校验 manifest、展开实验矩阵并逐个执行。

    命令行参数：
        --manifest：实验清单 JSON 路径（必填）。
        --output-dir：输出根目录，实际会再拼上 suite 名作为子目录。
        --dry-run：只打印将要执行的命令，不真正运行。
        --no-run：只校验 manifest，不展开也不运行。
        --resume：跳过已产出完整 summary 的运行（失败的会重试）。
        --force：跳过运行数量/深代数/需确认等安全检查。
        --shared-pool-dir：跨进程共享池目录，启用岛屿模型的种群共享。
    产出：每个实验一个输出子目录，最终写出汇总 run_index.json。
    """
    parser = argparse.ArgumentParser(description="Run experiments from a manifest JSON")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/auto_experiment_reports")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--no-run", action="store_true", help="Validate manifest only")
    parser.add_argument("--resume", action="store_true", help="Skip runs with existing summary")
    parser.add_argument("--force", action="store_true", help="Skip run-count safety check")
    parser.add_argument("--shared-pool-dir", default="", help="Cross-process shared pool for island model population sharing")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        sys.exit(f"Manifest not found: {args.manifest}")

    # 读取并解析实验清单 JSON
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # 先做静态校验，有错则打印全部错误并退出，避免带病运行
    errors = _validate_manifest(manifest)
    if errors:
        print("Manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    total_runs = _matrix_count(manifest)
    max_runs = manifest.get("max_runs", 2)
    suite = manifest["suite"]
    output_root = Path(args.output_dir).resolve() / suite
    shared_pool_dir = args.shared_pool_dir or ""

    gens = manifest.get("generations", [1])
    has_deep_gen = any(g > 1 for g in gens)  # 是否存在深代数（> 1）运行，耗时较大需额外确认
    require_confirm = manifest.get("require_confirm_for_real_run", True)

    # 三重安全闸门：真正执行前拦截超量/深代数/需人工确认的情况；--force 可整体跳过
    if not args.force and not args.dry_run and not args.no_run:
        if total_runs > max_runs:
            print(f"ERROR: expanded runs ({total_runs}) exceed max_runs ({max_runs}).")
            print(f"Use --dry-run to preview, --force to override, or reduce the manifest matrix.")
            sys.exit(1)
        if has_deep_gen:
            print(f"ERROR: generations contain > 1 ({gens}). Deep runs require explicit confirmation.")
            print(f"Use --force to override, or reduce max generation to 0 or 1.")
            sys.exit(1)
        if require_confirm:
            print(f"ERROR: manifest requires confirmation for real runs (require_confirm_for_real_run=true).")
            print(f"Use --force to acknowledge.")
            sys.exit(1)

    if not args.no_run:
        output_root.mkdir(parents=True, exist_ok=True)

    print(f"Suite: {suite}")
    print(f"Matrix: {len(manifest['problems'])}×{len(manifest['arms'])}×{len(manifest.get('generations',[1]))}×{manifest.get('repeats',1)} = {total_runs} runs")
    print()

    run_index: list[dict[str, Any]] = []
    problems = manifest["problems"]
    arms = manifest["arms"]
    generations = manifest.get("generations", [0])
    repeats = manifest.get("repeats", 1)

    # 四重笛卡尔展开：问题 → 实验臂 → 代数 → 重复；逐个坐标生成并执行一次运行
    for p_idx, problem in enumerate(problems):
        for a_idx, arm in enumerate(arms):
            # 允许某个臂只在部分问题上跑；当前问题不在其列表内则跳过
            arm_problems = arm.get("problems", problems)
            if problem not in arm_problems:
                continue
            rag = {**manifest.get("rag", {}), **arm.get("rag", {})}
            for gen in generations:
                prev_run_dir = ""  # 同一 (问题,臂,代数) 下按重复顺序链式传递上一次运行目录
                for rep in range(1, repeats + 1):
                    run_tag = f"run_{problem}_{arm['name']}_g{gen}_r{rep}"
                    run_out = str(output_root / run_tag)

                    # 预演模式：只打印命令，不执行；仍串好 prev_run_dir 以便预览链式关系
                    if args.dry_run:
                        cmd = _build_cmd(manifest, problem, arm, gen, rep, run_out, prev_run_dir=prev_run_dir)
                        print(f"[DRY] {run_tag}")
                        print(f"  {' '.join(cmd)}")
                        print()
                        prev_run_dir = run_out
                        continue

                    if args.no_run:
                        continue

                    # 断点续跑：已存在且成功的 summary 直接跳过；失败的则重试
                    summary_path = Path(run_out) / "official_eoh_run_summary.json"
                    if args.resume and summary_path.exists():
                        prev = json.loads(summary_path.read_text(encoding="utf-8"))
                        if not prev.get("failure_reason") and prev.get("run_summary", {}).get("ok"):
                            print(f"[SKIP] {run_tag} (already complete)")
                            prev_run_dir = run_out
                            continue
                        else:
                            print(f"[RETRY] {run_tag} (previous run failed: {prev.get('failure_reason','unknown')})")

                    print(f"[RUN] {run_tag}  start={time.strftime('%H:%M:%S')}")
                    # Island model: 从共享池取更优 seed（PoolAPI 统一入口）
                    effective_prev = prev_run_dir
                    seed_codes_path = ""
                    if shared_pool_dir:
                        pool = PoolAPI(shared_pool_dir)
                        # 若共享池里有比本地链更优的运行，改用它作为种子来源
                        pool_best = pool.best_run(problem)
                        if pool_best and pool_best != prev_run_dir:
                            effective_prev = pool_best
                        # 取池中最优的若干份代码，落盘成种子文件供子进程读取（进程号隔离，避免互相覆盖）
                        best_codes = pool.best_codes(problem, top_k=3)
                        if best_codes:
                            seed_codes_path = str(Path(shared_pool_dir) / f"_seed_{problem}_{os.getpid()}.json")
                            Path(seed_codes_path).write_text(json.dumps(best_codes, ensure_ascii=False), encoding="utf-8")
                    cmd = _build_cmd(manifest, problem, arm, gen, rep, run_out, prev_run_dir=effective_prev, seed_codes_path=seed_codes_path)
                    started = time.time()
                    # 真正拉起子进程执行单次运行；超时按 timeout 处理，比运行超时多留 60 秒缓冲
                    try:
                        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=manifest.get("run_timeout_s", 1800) + 60)
                        status = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
                    except subprocess.TimeoutExpired:
                        status = "timeout"
                    elapsed = round(time.time() - started, 1)

                    # 先记录一条基础运行结果（状态/耗时/输出目录等）到运行索引
                    run_index.append({
                        "tag": run_tag,
                        "problem": problem,
                        "arm": arm["name"],
                        "generation": gen,
                        "repeat": rep,
                        "status": status,
                        "runtime_s": elapsed,
                        "output_dir": run_out,
                    })

                    # 若产出了 summary，则补充最优目标值等信息
                    summary_ok = False       # run_summary 内部是否标记 ok
                    summary_failed = False   # summary 是否给出了 failure_reason
                    if summary_path.exists():
                        summary = json.loads(summary_path.read_text(encoding="utf-8"))
                        run_sum = summary.get("run_summary", {})
                        run_index[-1]["best_objective"] = run_sum.get("best_objective")
                        run_index[-1]["valid_candidates"] = run_sum.get("valid_candidates")
                        summary_ok = bool(run_sum.get("ok"))
                        fail_reason = summary.get("failure_reason")
                        if fail_reason:
                            summary_failed = True
                            run_index[-1]["failure_reason"] = fail_reason
                            # 进程返回 0 但 summary 内部标记失败：单独标注这种不一致状态
                            if status == "ok":
                                run_index[-1]["status"] = "ok_but_summary_failure"

                    print(f"[DONE] {run_tag}  status={status}  elapsed={elapsed}s")
                    # 判定本次是否成功：进程正常退出、summary 未标记失败、run_summary 标记 ok，三者都满足才算成功。
                    # 任一不满足就断开链式传递，避免超时 / 缺种群 / 内部失败的运行被当成功回写共享池。
                    if status == "ok" and summary_ok and not summary_failed:
                        prev_run_dir = run_out
                        # Island model: register successful run in shared pool
                        # 成功结果回写共享池，供其它进程作为种子共享（岛屿模型）
                        if shared_pool_dir and summary_path.exists():
                            try:
                                sm = json.loads(summary_path.read_text(encoding="utf-8"))
                                obj = (sm.get("run_summary") or {}).get("best_objective")
                                code = (sm.get("run_summary") or {}).get("best_code", "")
                                if obj is not None:
                                    pool = PoolAPI(shared_pool_dir)
                                    # Adaptive operator: compare BEFORE registering
                                    # 自适应算子：先取回写前池中最优值，用于判断本次是否带来提升
                                    pool_codes_before = pool.best_codes(problem, top_k=1)
                                    prev_best = pool_codes_before[0]["objective"] if pool_codes_before else None

                                    # 回写本次运行目录与最优代码；显著提升时顺带合成算法卡片
                                    pool.register_run(problem, run_out, obj)
                                    if code:
                                        pool.register_code(problem, code, obj)
                                        _maybe_synthesize_card(shared_pool_dir, problem, code, obj)

                                    # Register operator result with correct ordering
                                    # 用「回写前」的最优值比较，统计算子组合的提升表现
                                    if prev_best is not None:
                                        improved = obj < prev_best
                                        delta = (prev_best - obj) / abs(prev_best) if prev_best else 0
                                        operators_str = manifest.get("operators", "e1,e2,m1,m2")
                                        pool.register_operator_stat(problem, operators_str, improved, delta)
                            except Exception:
                                logger.exception("shared_pool_register failed")
                        # Online outcome update
                        # 在线效果回流：把本次 RAG 注入的效果记录追加到 outcome 文件
                        if summary_path.exists():
                            outcome_file = rag.get("outcome_file", "")
                            if outcome_file:
                                _append_online_outcome(summary_path, problem, outcome_file)
                    else:
                        prev_run_dir = ""  # 本次失败，断开链式传递，下一次重复从头开始
                        # Failure pattern sharing
                        # 失败模式共享：把失败的代码与原因登记到共享池，供后续避坑
                        if shared_pool_dir and summary_path.exists():
                            try:
                                sm = json.loads(summary_path.read_text(encoding="utf-8"))
                                rs = sm.get("run_summary") or {}
                                fail_reason = sm.get("failure_reason", "")
                                code = rs.get("best_code", "")
                                if fail_reason and code:
                                    PoolAPI(shared_pool_dir).register_failure(problem, code, fail_reason)
                            except Exception:
                                logger.exception("failure_sharing failed")

    # 全部跑完后，把汇总的运行索引写盘（预演/仅校验模式不写）
    if not args.dry_run and not args.no_run:
        index_path = output_root / "run_index.json"
        index_path.write_text(json.dumps(run_index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRun index written to {index_path}")


if __name__ == "__main__":
    main()
