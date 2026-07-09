"""
模块：TOCC 有界自动循环试点（bounded auto-loop pilot）
功能：以严格受控的预算，自动驱动"读取运行轨迹 → 提议改进方案 → 安全校验 → 生成清单 →（可选真实执行）→ 观测新轨迹"这一闭环，用于演化组合优化问题（在线装箱、TSP、CVRP、InsertShips）的启发式算法。
职责：管理循环状态（当前轨迹、历史记录、上一轮运行目录），编排各个子模块进程（控制器 / 流水线 / 批量执行器），并对每一轮的提议、清单、运行结果与新轨迹进行落盘记录。
接口：
  - run_v3_loop(start_trace_path, *, problem, available_cards, output_dir, max_iterations=2, real_run=False) -> list[dict]
    执行整个有界循环，返回逐轮历史记录列表。
  - main() -> None
    命令行入口，解析参数并调用 run_v3_loop，最后把历史写入 JSON。
输入：起始轨迹文件路径、问题名称、可用知识卡片 ID 列表、输出目录；命令行参数 --trace / --problem / --cards / --output-dir / --max-iterations / --confirm-paid。
输出：每轮生成的 mini-manifest 清单文件、真实运行产物，以及汇总的循环历史 v3_loop_history.json。
示例：
  python -m eoh_rag.tocc.loop --trace trace_0.json --problem bin_packing --cards cardA,cardB
说明：
  - 预算硬约束：max_iterations 上限为 2，每轮世代数 gen≤1、运行数 runs≤4；提议方无权修改预算。
  - 默认走 dry-run（不调用付费 API）；只有显式传入 --confirm-paid 才会真实执行。
  - 一轮闭环形态：trace_0 → 代理提议 → 安全校验（gatekeeper）→ 生成清单 →（真实执行）→ trace_1。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eoh_rag.tocc.contracts import TOCC_CANDIDATE_POOL_STRATEGY

# 循环的迭代次数硬上限：预算受控，最多只跑 2 轮
MAX_ITERATIONS = 2


def run_v3_loop(
    start_trace_path: str,
    *,
    problem: str,
    available_cards: list[str],
    output_dir: str,
    max_iterations: int = MAX_ITERATIONS,
    real_run: bool = False,
) -> list[dict[str, Any]]:
    """执行有界自动循环，逐轮"读轨迹 → 提议 → 校验 → 生成清单 →（可选真实运行）→ 观测新轨迹"。

    关键参数：
      - start_trace_path：起始运行轨迹文件路径，作为第一轮提议的输入。
      - problem：目标优化问题名称（如 bin_packing、tsp、cvrp、insertships）。
      - available_cards：可供提议方选用的知识卡片 ID 列表。
      - output_dir：清单文件与运行产物的输出目录。
      - max_iterations：最大轮次，不得超过 MAX_ITERATIONS，否则抛出 ValueError。
      - real_run：为 False 时走 dry-run（本地规则控制器 + 预览，不调用付费 API）；为 True 时走真实执行（LLM 代理 + 批量执行器）。

    返回：逐轮历史记录列表，每个元素记录该轮的提议、校验、清单与运行结果等信息。
    """
    # 预算护栏：轮次不允许超过硬上限
    if max_iterations > MAX_ITERATIONS:
        raise ValueError(f"max_iterations ({max_iterations}) exceeds V3 limit ({MAX_ITERATIONS})")

    history: list[dict[str, Any]] = []
    current_trace = start_trace_path  # 当前用于提议的轨迹，会随真实运行更新
    prev_run_dir = ""  # 上一轮真实运行的输出目录，供检索阶段引用历史

    for iteration in range(1, max_iterations + 1):
        print(f"\n=== V3 iteration {iteration}/{max_iterations} ===")

        # 提议阶段：代理读取轨迹并给出一个"实验臂"（arm）方案
        if not real_run:
            # dry-run：使用规则型本地控制器（快、不调用 API）
            cmd = [
                sys.executable, "-m", "eoh_rag.tocc.controller",
                "--trace", current_trace,
            ]
        else:
            # 真实运行：使用 LLM 代理流水线来提议方案
            cmd = [
                sys.executable, "-m", "eoh_rag.tocc.pipeline",
                "--trace", current_trace,
                "--problem", problem,
                "--available-cards", ",".join(available_cards),
            ]
        print(f"[PROPOSE] reading trace...")
        # 以子进程方式调用提议方，限时 120 秒，捕获标准输出/错误
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        if result.returncode != 0:
            # 提议方进程失败：记录错误尾部并终止循环
            history.append({"iteration": iteration, "error": "proposer failed", "stderr": result.stderr[-500:]})
            break

        # 提议方通过 stdout 返回 JSON 结果
        try:
            proposal_raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            history.append({
                "iteration": iteration,
                "error": "proposer returned invalid json",
                "details": str(exc),
                "stdout": result.stdout[-500:],
                "stderr": result.stderr[-500:],
            })
            break

        if not real_run:
            # 规则控制器输出格式：{diagnosis, recommended_cards, recommended_query, ...}
            diagnosis = proposal_raw.get("diagnosis", "unknown")
            cards = proposal_raw.get("recommended_cards", [])
            query = proposal_raw.get("recommended_query", "")
            accepted = bool(cards)  # 有推荐卡片即视为可执行
            print(f"[V1] diagnosis={diagnosis}, cards={cards}")
            if not accepted:
                # 未推荐任何卡片：本轮无需动作，直接进入下一轮
                history.append({"iteration": iteration, "diagnosis": diagnosis, "cards": cards, "status": "no_cards_recommended"})
                print(f"[NO CARDS] V1 found no action needed")
                continue
            # 由规则控制器的推荐拼装出一个标准的实验臂
            safe_arm = {
                "name": f"v1_{diagnosis}",
                "runner_arm": "literature_rag",
                "context_strategy": TOCC_CANDIDATE_POOL_STRATEGY,
                "rag_query": query,
                "candidate_card_ids": cards,
            }
            gatekeeper = {}
        else:
            # LLM 代理输出格式：{accepted, safe_arm, gatekeeper, proposal}
            accepted = proposal_raw.get("accepted", False)
            safe_arm = proposal_raw.get("safe_arm")
            gatekeeper = proposal_raw.get("gatekeeper", {})
            # 兼容两种字段名：candidate_card_ids 或 selected_card_ids
            cards = (safe_arm.get("candidate_card_ids") or safe_arm.get("selected_card_ids") or []) if safe_arm else []
            query = safe_arm.get("rag_query", "") if safe_arm else ""
            diagnosis = proposal_raw.get("proposal", {}).get("diagnosis", "")
            print(f"[V2] accepted={accepted}, cards={cards}")

        # 记录本轮"已提议"阶段的关键信息
        history.append({
            "iteration": iteration,
            "phase": "proposed",
            "diagnosis": diagnosis,
            "cards": cards,
            "accepted": accepted,
        })

        if not accepted or not safe_arm:
            # 未通过安全校验或没有可用实验臂：打印违规项并终止循环
            print(f"[REJECTED] violations={gatekeeper.get('violations', [])}")
            break

        cards = safe_arm.get("candidate_card_ids") or safe_arm.get("selected_card_ids") or []
        query = safe_arm.get("rag_query", "")
        print(f"[ACCEPTED] cards={cards}")

        # 为本轮生成 mini-manifest（执行清单）：世代=0、pop_size=4、单次运行，预算严格受限
        suite = f"v3_pilot_iter{iteration}"
        manifest_path = Path(output_dir) / f"{suite}.json"
        manifest = {
            "suite": suite, "model": "JoyAI-LLM-Pro",
            "problems": [problem],
            "arms": [safe_arm],
            "generations": [0], "pop_size": 4, "repeats": 1,
            "max_runs": 1, "max_llm_calls_estimate": 8,
            "require_confirm_for_real_run": True,
            "operators": "i1", "run_timeout_s": 1800,
            # 检索配置：引用上一轮运行目录 prev_run_dir 作为历史上下文
            "rag": {"top_k": 2, "max_chars": 2500, "prev_run_dir": prev_run_dir},
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[MANIFEST] {manifest_path}")

        # 根据模式选择：dry-run 预览，或真实执行
        if not real_run:
            # dry-run：仅让批量执行器做一次预演，不真正跑实验
            print(f"[DRY] cards={cards}, query={query[:80]}...")
            dm_cmd = [
                sys.executable, "-m", "eoh_rag.experiments.batch_runner",
                "--manifest", str(manifest_path),
                "--output-dir", output_dir,
                "--dry-run",
            ]
            dry_proc = subprocess.run(dm_cmd, text=True, capture_output=True, timeout=30)
            history[-1]["run_result"] = "dry_run_only"
            history[-1]["dry_run_status"] = "ok" if dry_proc.returncode == 0 else f"exit_{dry_proc.returncode}"
            if dry_proc.returncode != 0:
                history[-1]["dry_run_stderr"] = dry_proc.stderr[-500:]
            # dry-run 一次即止:不设 fake trace,不继续循环(否则第二轮用字面量 "(would be new trace)" 空转)
            break

        # 真实执行：用 --force 让批量执行器实际跑实验，限时 2100 秒
        print(f"[RUN] cards={cards}")
        run_cmd = [
            sys.executable, "-m", "eoh_rag.experiments.batch_runner",
            "--manifest", str(manifest_path),
            "--output-dir", output_dir,
            "--force",
        ]
        proc = subprocess.run(run_cmd, text=True, capture_output=True, timeout=2100)
        history[-1]["run_status"] = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
        if proc.returncode != 0:
            # 运行失败：记录错误尾部并终止循环
            history[-1]["run_stderr"] = proc.stderr[-500:]
            print(f"[FAILED] exit={proc.returncode}")
            break

        # 观测阶段：读取本次运行产出的新轨迹与最优目标值，作为下一轮的输入
        suite_dir = Path(output_dir) / suite
        index_path = suite_dir / "run_index.json"
        if index_path.exists():
            try:
                idx = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                history[-1]["error"] = "run_index unreadable"
                history[-1]["details"] = str(exc)
                break
            if idx:
                # 从运行索引里定位到本次运行的汇总文件
                first_run = idx[0]
                run_output_dir = first_run.get("output_dir", "")
                if not run_output_dir:
                    history[-1]["error"] = "run_index missing output_dir"; break
                new_summary = Path(run_output_dir) / "official_eoh_run_summary.json"
                if new_summary.exists():
                    current_trace = str(new_summary)  # 用新汇总作为下一轮的轨迹输入
                    history[-1]["new_trace"] = str(new_summary)
                    history[-1]["best_objective"] = first_run.get("best_objective")
                    prev_run_dir = run_output_dir  # 记录本轮目录，供下一轮检索引用
                    print(f"[OBSERVE] best={first_run.get('best_objective')}")
                else:
                    # 找不到汇总文件：记录错误并终止
                    history[-1]["error"] = "summary not found"; break
            else:
                # 运行索引为空：记录错误并终止
                history[-1]["error"] = "run_index empty"; break
        else:
            # 运行索引文件不存在：记录错误并终止
            history[-1]["error"] = "run_index not found"; break

        time.sleep(1)  # 轮次之间稍作停顿，避免过快连续触发子进程

    return history


def main() -> None:
    """命令行入口：解析参数、校验付费确认、运行有界循环，并把历史写入 JSON。"""
    import argparse

    parser = argparse.ArgumentParser(description="TOCC V3 bounded auto-loop pilot")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/auto_experiment_reports/v3_pilot")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--confirm-paid", action="store_true",
                        help="Confirm paid API execution (required for real-run)")
    args = parser.parse_args()

    # 把逗号分隔的卡片字符串拆成列表，并逐项去除首尾空白
    available = [c.strip() for c in args.cards.split(",")]
    output_dir = Path.cwd() / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 安全护栏：只有显式传入 --confirm-paid 才会真实调用付费 API
    if args.confirm_paid:
        print("⚠️  CONFIRMED: paid API execution with JoyAI-LLM-Pro")
    else:
        print("DRY-RUN mode (use --confirm-paid for real execution)")

    history = run_v3_loop(
        args.trace, problem=args.problem, available_cards=available,
        output_dir=str(output_dir), max_iterations=args.max_iterations,
        real_run=args.confirm_paid,
    )

    # 汇总的逐轮历史落盘为 JSON
    out = output_dir / "v3_loop_history.json"
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nLoop history: {out}")


if __name__ == "__main__":
    main()
