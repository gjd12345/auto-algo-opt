"""
模块：TOCC Agent（Trace-Conditioned Operator-Card Controller 智能体）
功能：读取一次 EOH 运行的轨迹（trace），调用大模型（LLM）诊断本次搜索的失败模式，
      并提议下一轮应当使用的「算子卡片」（operator card）候选池与检索查询语句。
职责：
  - 把运行汇总 JSON 展平成结构化的诊断输入（_flatten_trace）；
  - 依据轨迹拼装给 LLM 的用户提示词（_build_user_prompt）；
  - 调用 LLM 并解析其返回的 JSON 提议（propose）。
  说明：本智能体只负责「提议」，不做最终的卡片注入决策，注入由检索/重排环节把关。
接口：
  - propose(summary_path, *, model, api_key, endpoint, temperature, timeout_s, max_retries) -> dict
      返回 {"proposal": {...}, "gatekeeper": {...}, "error": None}
  - _flatten_trace(summary_path) -> dict：展平运行汇总为诊断字段
  - _build_user_prompt(trace) -> str：把诊断字段拼成 LLM 用户提示词
输入：
  - summary_path：一次运行的汇总文件路径（official_eoh_run_summary.json）；
  - 环境变量：DEEPSEEK_MODEL / DEEPSEEK_API_KEY / DEEPSEEK_API_ENDPOINT（可被入参覆盖）。
输出：
  - 一个包含 LLM 提议（诊断类型、候选卡片列表、检索查询、理由、风险、下一步动作）的字典。
示例：
    result = propose("outputs/official_eoh_run_summary.json")
    if result["error"] is None:
        print(result["proposal"]["diagnosis"])

面向大模型的说明：本模块解决「基于轨迹诊断，为下一轮进化选卡」的问题；
LLM 仅产出候选，最终注入由检索/重排把关。
"""

# TOCC V2 Agent — LLM proposer for operator-card selection.
#
# Reads run traces, calls LLM to propose next card set + query.
# LLM only proposes; gatekeeper enforces.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from eoh_rag.tocc.controller import (
    BASELINE_OVERLAP_CARDS,
    TARGETED_CANDIDATE_CARDS,
    CARD_QUERIES,
    _get_code_family,
)


# 系统提示词：约束 LLM 扮演「TOCC 诊断专家」，规定其必须输出的 JSON 字段、
# 可选的 10 种诊断类型、6 种下一步动作类型，以及选卡规则（前缀约束、候选来源、
# 多样性/纠偏建议、候选数量与查询长度上限等）。内容为固定契约，供 LLM 调用直接使用。
SYSTEM_PROMPT = """You are a TOCC (Trace-Conditioned Operator-Card Controller) diagnosis specialist.
You analyze EOH (Evolutionary Heuristic Optimization) run traces for combinatorial optimization problems.

Your job: read the run trace, diagnose the failure mode, and propose the next operator-card candidate pool.

Output must be valid JSON with exactly these fields:
{
  "diagnosis": "<one of 10 types>",
  "candidate_card_ids": ["<card_id_1>", "<card_id_2>", "..."],
  "query": "<rag query string>",
  "why": ["<reason 1>", "<reason 2>"],
  "risk": "<risk warning>",
  "next_action": "<one of 6 action types>"
}

Diagnosis types:
- baseline_overlap: selected cards overlap with pure EOH baseline family (e.g., nearest, best-fit). Cards don't change search direction.
- wrong_bias: selected cards bias search in wrong direction (e.g., capacity-first when distance should be primary).
- low_diversity: multiple samples produce near-identical code with same objective.
- context_truncated: RAG context was truncated, card content may be incomplete.
- valid_collapse: valid candidate rate is very low, generation or evaluation is failing.
- api_failure: API calls failed, run is incomplete.
- budget_mismatch: arms have different gen/pop/repeats settings.
- no_issue: no failure mode detected, maintain current cards.
- weak_negative: best objective worse than pure baseline or known targeted best, cards should be changed.
- inconclusive: best objective near pure baseline, no clear signal — needs more runs or different cards.

Next action types:
- run_init_only: run a single init-only smoke with proposed cards.
- retry: re-run the same configuration.
- expand_generations: increase generations for deeper search.
- maintain: keep current configuration.
- manual_review: proposal needs human review before executing.
- run_repeat: run multiple repeats to verify stability.

Rules:
1. Cards must start with the problem prefix (tsp_ for tsp_construct, cvrp_ for cvrp_construct).
2. Only propose candidate_card_ids from the available pool listed in the trace.
3. If baseline_overlap, propose targeted diversity cards (regret, farthest, residual, savings).
4. If wrong_bias, propose cards that correct the bias direction.
5. You are not the final card injector. Propose a candidate pool; retrieval/rerank selects final top_k injected cards.
6. Prefer 4-8 candidate_card_ids when enough cards are available. If fewer than 4 are available, return the available useful candidates and explain the limitation in why.
7. Query must be under 500 characters."""


def _flatten_trace(summary_path: str) -> dict[str, Any]:
    """从运行汇总文件中抽取并展平诊断所需的轨迹字段。

    读取 official_eoh_run_summary.json，把其中的检索轨迹（rag_trace）与
    运行汇总（run_summary）合并成一个扁平字典，供后续拼装 LLM 提示词使用。

    参数：
        summary_path：运行汇总 JSON 文件的路径。
    返回：
        一个字典，包含问题名、实验臂、检索查询、已选卡片及其分数、候选池信息、
        各类告警、有效候选数、最优目标值、代码特征，以及用于对比诊断的历史基线值等。
    """
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    rag = payload.get("rag_trace") or {}
    run_sum = payload.get("run_summary") or {}

    # best_code：本轮最优个体的源码；据此提取「代码家族/特征」用于诊断偏置与多样性
    best_code = run_sum.get("best_code", "")
    code_family = list(_get_code_family(best_code))
    population_features = list(rag.get("rag_population_features") or [])

    return {
        "problem": payload.get("problem", ""),
        "arm": payload.get("arm", ""),
        "rag_query": rag.get("rag_query"),
        "rag_selected_items": [item.get("id", "") for item in rag.get("rag_selected_items", [])],
        "rag_selected_titles": [item.get("title", "") for item in rag.get("rag_selected_items", [])],
        "rag_all_scores": [{"id": s["id"], "score": s["score"]} for s in rag.get("rag_all_scores", [])],
        "rag_context_chars": rag.get("rag_context_chars"),
        "rag_max_chars": rag.get("rag_max_chars"),
        "rag_strategy_pool_size": rag.get("rag_strategy_pool_size"),
        "rag_candidate_card_ids": rag.get("rag_candidate_card_ids", []),
        "rag_candidate_card_source": rag.get("rag_candidate_card_source"),
        "rag_candidate_pool_size_before_filter": rag.get("rag_candidate_pool_size_before_filter"),
        "rag_candidate_pool_size_after_filter": rag.get("rag_candidate_pool_size_after_filter"),
        "rag_selection_space_warning": rag.get("rag_selection_space_warning", []),
        "candidate_cards_with_zero_keyword_score": rag.get("candidate_cards_with_zero_keyword_score", []),
        "candidate_cards_dropped_by_zero_keyword_score": rag.get(
            "candidate_cards_dropped_by_zero_keyword_score", []
        ),
        "rag_candidate_zero_score_warning": rag.get("rag_candidate_zero_score_warning", []),
        "rag_rerank_enabled": rag.get("rag_rerank_enabled"),
        "rag_rerank_scores": list(rag.get("rag_rerank_scores") or [])[:8],
        "rag_outcome_summary_count": rag.get("rag_outcome_summary_count"),
        "rag_population_feature_count": len(population_features),
        "rag_population_features": population_features[:20],
        "valid_candidates": run_sum.get("valid_candidates"),
        "population_size": run_sum.get("population_size"),
        "best_objective": run_sum.get("best_objective"),
        "code_family": code_family,
        "failure_reason": payload.get("failure_reason"),
        "runtime_seconds": payload.get("runtime_seconds"),
        # 可用卡片池 = 该问题的「定向候选卡」+「与基线重叠的卡」；供 LLM 从中挑选候选
        "available_cards": TARGETED_CANDIDATE_CARDS.get(payload.get("problem", ""), []) +
                           list(BASELINE_OVERLAP_CARDS.get(payload.get("problem", ""), set())),
        "baseline_cards": list(BASELINE_OVERLAP_CARDS.get(payload.get("problem", ""), set())),
        # 历史基线：纯 EOH 最优、定向最优及其对应卡片，用于横向对比判断本轮好坏
        "pure_eoh_best": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("pure"),
        "historical_best": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("targeted"),
        "historical_best_cards": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("cards", []),
    }


# 各问题的已知最优目标值，用于对比诊断：pure=纯 EOH 基线，targeted=使用定向卡的最优，
# cards=达到定向最优时所用的卡片。目标值越小越好（如路径长度/装箱代价）。
_BASELINE_OBJECTIVES = {
    "tsp_construct": {"pure": 6.839, "targeted": 6.217, "cards": ["tsp_regret_insertion", "tsp_farthest_insertion"]},
    "cvrp_construct": {"pure": 13.207, "targeted": 12.821, "cards": ["cvrp_regret_insertion", "cvrp_far_first"]},
}


def _build_user_prompt(trace: dict[str, Any]) -> str:
    """把展平后的轨迹拼装成给 LLM 的用户提示词字符串。

    将问题、实验臂、检索查询、候选池、已选卡片与分数、各类告警、历史基线对比等
    逐行罗列，并在末尾给出对比判断规则与「只输出 JSON」的要求。

    参数：
        trace：_flatten_trace 返回的扁平轨迹字典。
    返回：
        多行提示词字符串（各行以换行拼接）。
    """
    items = trace.get("rag_selected_items", [])
    titles = trace.get("rag_selected_titles", [])
    scores = trace.get("rag_all_scores", [])
    candidate_ids = trace.get("rag_candidate_card_ids", [])
    rerank_scores = trace.get("rag_rerank_scores", [])

    parts = [
        f"Problem: {trace.get('problem')}",
        f"Arm: {trace.get('arm')}",
        f"RAG Query: {trace.get('rag_query')}",
        (
            f"Candidate Pool: {trace.get('rag_candidate_card_source') or 'none'} "
            f"({trace.get('rag_candidate_pool_size_after_filter')}/"
            f"{trace.get('rag_candidate_pool_size_before_filter')}): {candidate_ids}"
        ),
        f"Selected Cards ({len(items)}): {', '.join(f'{i}({t})' for i, t in zip(items, titles))}",
        f"Card Scores: {', '.join(s['id'] + '=' + str(s['score']) for s in scores[:5])}",
        f"Rerank Enabled: {trace.get('rag_rerank_enabled')}",
        f"Outcome Summary Count: {trace.get('rag_outcome_summary_count')}",
        f"Population Feature Count: {trace.get('rag_population_feature_count')}",
        f"Population Features: {trace.get('rag_population_features', [])}",
        f"Selection Warnings: {trace.get('rag_selection_space_warning', [])}",
        f"Zero-score Candidate Warning: {trace.get('rag_candidate_zero_score_warning', [])}",
        (
            "Dropped Zero-score Candidates: "
            f"{trace.get('candidate_cards_dropped_by_zero_keyword_score', [])}"
        ),
        f"Top Rerank Scores: {json.dumps(rerank_scores, ensure_ascii=False)}",
        f"Context: {trace.get('rag_context_chars')}/{trace.get('rag_max_chars')} chars, pool_size={trace.get('rag_strategy_pool_size')}",
        f"Valid Candidates: {trace.get('valid_candidates')}/{trace.get('population_size')}",
        f"Best Objective: {trace.get('best_objective')}",
        f"Code Features: {trace.get('code_family')}",
        f"Failure: {trace.get('failure_reason') or 'none'}",
        f"Runtime: {trace.get('runtime_seconds')}s",
        f"Available Card IDs: {trace.get('available_cards')}",
        f"Baseline Cards (overlap candidates): {trace.get('baseline_cards')}",
        f"Historical Baseline: pure_eoh={trace.get('pure_eoh_best')}",
        f"Historical Best Targeted: {trace.get('historical_best')} (cards={trace.get('historical_best_cards')})",
        "",
        "Compare current Best Objective against Historical Baseline and Historical Best Targeted.",
        "If current is worse than historical targeted, diagnose weak_negative and recommend different cards.",
        "If current is within noise of pure baseline, diagnose inconclusive.",
        "Based on this trace and comparisons, diagnose the failure mode and propose the next card set.",
        "Output only valid JSON, no other text.",
    ]
    return "\n".join(parts)


def propose(
    summary_path: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
    temperature: float = 0.3,
    timeout_s: int = 60,
    max_retries: int = 3,
) -> dict[str, Any]:
    """根据一次运行的轨迹，调用 LLM 提议下一轮的卡片候选集与检索查询。

    流程：读取模型/密钥/端点（入参优先，缺省回退到环境变量）→ 展平轨迹并拼装提示词
    → 调用 LLM（要求返回 JSON）→ 解析返回并封装结果。

    参数：
        summary_path：运行汇总 JSON 文件路径。
        model / api_key / endpoint：LLM 模型名、密钥、访问端点；未传时读取对应环境变量。
        temperature：采样温度，越低越确定。
        timeout_s：单次请求超时秒数。
        max_retries：失败重试次数。
    返回：
        字典 {"proposal": {...}|None, "gatekeeper": None, "error": None|错误信息}。
        当缺少凭证、请求异常或 JSON 解析失败时，proposal 为 None 且 error 说明原因。
    """
    from eoh_rag.llm.client import chat_completion

    # 凭证与模型：入参优先，未提供则回退到环境变量（DEEPSEEK_* 系列）
    model = model or os.environ.get("DEEPSEEK_MODEL", "JoyAI-LLM-Pro")
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    endpoint = endpoint or os.environ.get("DEEPSEEK_API_ENDPOINT", "")

    if not api_key or not endpoint:
        return {"proposal": None, "gatekeeper": None, "error": "missing API credentials"}

    trace = _flatten_trace(summary_path)
    user_prompt = _build_user_prompt(trace)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        content = chat_completion(
            messages,
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            temperature=temperature,
            timeout_s=timeout_s,
            max_retries=max_retries,
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
    except RuntimeError as e:
        return {"proposal": None, "gatekeeper": None, "error": str(e)}

    # 兼容 LLM 把 JSON 包在 markdown 代码块（```json ... ```）里的情况：
    # 取出代码块内容，并去掉可能的 json 语言标记，再做解析
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    try:
        proposal = json.loads(content.strip())
    except json.JSONDecodeError as e:
        return {"proposal": None, "gatekeeper": None, "error": f"JSON parse failed: {e}"}

    return {"proposal": proposal, "gatekeeper": None, "error": None}
