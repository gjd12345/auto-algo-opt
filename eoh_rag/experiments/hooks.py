"""
模块：hooks —— 实验 run 生命周期事件处理
功能：把 batch_runner 中 pool 注册、card 合成、outcome 更新等副作用逻辑统一收拢，
      batch_runner 主循环只需调 on_run_success / on_run_failure。
职责：
  - on_run_success: 注册 pool / code / operator_stat → 评估 → 条件合成 card → 追加 outcome
  - on_run_failure: 注册 failure pattern
不负责：
  - run 的调度和 subprocess 管理（属 batch_runner）
  - PoolAPI 内部的 JSONL 读写（属 pool_api）
  - evaluator 的评价逻辑（属 evaluator）

主要调用方：batch_runner.py（替代内联 try-except 块）

接口：
    on_run_success(pool, problem, run_dir, summary, manifest, outcome_file="") → dict
    on_run_failure(pool, problem, summary) → None

输入：PoolAPI 实例 + run 上下文
输出：on_run_success 返回 evaluator 结果 dict

示例：
    from eoh_rag.experiments.hooks import on_run_success, on_run_failure
    from eoh_rag.experiments.pool_api import PoolAPI
    pool = PoolAPI("shared_pool")
    eval_result = on_run_success(pool, "bp_online", "/run/1", summary_dict, manifest_dict)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from eoh_rag.experiments.baselines import get_baseline
from eoh_rag.experiments.evaluator import evaluate_run
from eoh_rag.experiments.pool_api import PoolAPI
from eoh_rag.utils.file_lock import exclusive_lock

logger = logging.getLogger(__name__)


def on_run_success(
    pool: PoolAPI,
    problem: str,
    run_dir: str,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    outcome_file: str = "",
) -> dict[str, Any]:
    """run 成功后的所有副作用。返回 evaluator 结果。"""
    run_summary = summary.get("run_summary") or {}
    obj = run_summary.get("best_objective")
    code = run_summary.get("best_code", "")

    eval_result: dict[str, Any] = {}

    if obj is not None:
        # 评估
        eval_result = evaluate_run(problem, obj)

        # 先读旧 best 用于 operator delta 计算
        pool_codes_before = pool.best_codes(problem, top_k=1)
        prev_best = pool_codes_before[0]["objective"] if pool_codes_before else None

        # 注册 run + code
        pool.register_run(problem, run_dir, obj)
        if code:
            pool.register_code(problem, code, obj)
            # 条件合成 card
            if eval_result.get("passed"):
                _maybe_synthesize_card(problem, code, obj)

        # 注册 operator stat
        if prev_best is not None:
            improved = obj < prev_best
            delta = (prev_best - obj) / abs(prev_best) if prev_best else 0
            operators_str = manifest.get("operators", "e1,e2,m1,m2")
            pool.register_operator_stat(problem, operators_str, improved, delta)

    # 追加 online outcome（RAG 注入效果追踪）
    if outcome_file:
        _append_online_outcome(summary, problem, run_dir, outcome_file)

    return eval_result


def on_run_failure(
    pool: PoolAPI,
    problem: str,
    summary: dict[str, Any],
) -> None:
    """run 失败后注册失败模式。"""
    run_summary = summary.get("run_summary") or {}
    fail_reason = summary.get("failure_reason", "")
    code = run_summary.get("best_code", "")
    if fail_reason and code:
        pool.register_failure(problem, code, fail_reason)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _maybe_synthesize_card(problem: str, code: str, objective: float) -> None:
    """当 evaluator 判定 archive 时触发 card 合成。"""
    try:
        from eoh_rag.rag.card_synthesis import synthesize_card
        from eoh_rag.rag.schemas import load_corpus

        corpus_path = Path("eoh_rag_workspace/rag/corpus/algorithm_cards.jsonl")
        card = synthesize_card(problem, code, run_info={"objective": objective})
        existing = load_corpus(corpus_path)
        if any(c.id == card.id for c in existing):
            return
        with open(corpus_path, "a", encoding="utf-8") as f:
            with exclusive_lock(f):
                f.write(json.dumps(card.__dict__, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("card_synthesis failed")


def _append_online_outcome(summary: dict, problem: str, run_dir: str, outcome_file: str) -> None:
    """从 summary 中提取 RAG 注入效果并追加到 outcome 文件。"""
    try:
        from eoh_rag.rag.card_outcomes import build_outcome_records, save_outcomes

        rag_trace = summary.get("rag_trace") or {}
        run_summary = summary.get("run_summary") or {}
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
            # 以问题的官方基线作为纯基线，让 delta_pct 与 objective_success 可算，形成在线反馈闭环。
            "pure_baseline": get_baseline(problem),
        }
        # 用 run 目录名作为唯一 run_id，避免固定键在多 run 间去重冲突。
        run_id = Path(run_dir).name or "online_outcome"
        records = build_outcome_records(
            run_id=run_id,
            problem=problem,
            generation=run_summary.get("latest_generation", 4),
            injection_audit=injection_audit,
            generation_result=gen_result,
        )
        if records and outcome_file:
            save_outcomes(records, Path(outcome_file), append=True)
    except Exception:
        logger.exception("online_outcome_update failed")


__all__ = ["on_run_success", "on_run_failure"]
