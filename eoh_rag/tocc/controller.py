"""
模块：TOCC（Trace-Conditioned Operator-Card Controller，基于运行轨迹的算子卡片控制器）
功能：读取一次启发式演化运行的轨迹摘要，用纯规则诊断本次运行出现的问题，并给出应更换的算子卡片集合与检索查询词。
职责：管理问题相关的先验知识（基线卡片、候选卡片、卡片对应的检索关键词），并把轨迹字典映射为一个诊断结论。
接口：
    - diagnose(trace: dict) -> TOCCDecision：核心诊断函数，输入轨迹字典，返回诊断结论对象。
    - TOCCDecision：承载诊断结果的数据类（问题名、诊断类型、推荐卡片、推荐查询词、原因、风险、下一步动作）。
    - main() -> None：命令行入口，读取轨迹 JSON 文件并打印/写出诊断结果。
输入：一个官方运行摘要 JSON 文件（其中含 problem、arm、rag_trace、run_summary 等字段）。
输出：一段 JSON，包含诊断类型与推荐的卡片、查询词、原因、风险和下一步动作。
说明：本模块只做规则判断，不调用大模型，也不修改任何文件。
示例：
    python -m eoh_rag.tocc.controller --trace official_eoh_run_summary.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eoh_rag.tocc.card_decisions import (
    DEPRIORITIZED_DECISIONS,
    HARD_BLOCK_DECISIONS,
    WATCHLIST_DECISIONS,
    load_card_prior_decisions,
)


# --- 问题相关的先验知识 ---

# 各优化问题的“基线卡片”集合：这些卡片代表最朴素的经典构造策略。
# 若一次运行选中的卡片落在这里，往往说明检索没有真正改变搜索方向。
BASELINE_OVERLAP_CARDS: dict[str, set[str]] = {
    "tsp_construct": {"tsp_nearest_neighbor", "tsp_nearest_insertion"},
    "cvrp_construct": {"cvrp_nearest_capacity", "cvrp_capacity_slack"},
    "bp_online": {"obp_first_fit", "obp_best_fit", "obp_worst_fit"},
}

# 各优化问题的“有针对性的候选卡片”：当基线卡片无效时，用来替换、引导更有前景的搜索方向。
TARGETED_CANDIDATE_CARDS: dict[str, list[str]] = {
    "tsp_construct": ["tsp_regret_insertion", "tsp_farthest_insertion", "tsp_two_opt_awareness"],
    "cvrp_construct": ["cvrp_regret_insertion", "cvrp_far_first", "cvrp_savings", "cvrp_sweep"],
    "bp_online": ["obp_funsearch_residual_poly", "obp_eoh_util_sqrt_exp", "obp_harmonic"],
}

# 每张候选卡片对应的检索关键词：用于拼装推荐查询词，帮助检索更精准地命中该策略的资料。
CARD_QUERIES: dict[str, str] = {
    "tsp_regret_insertion": "tsp regret lookahead second best insertion route length",
    "tsp_farthest_insertion": "tsp farthest cluster insertion distant node route",
    "tsp_two_opt_awareness": "tsp local smooth crossing edge avoid long edge",
    "cvrp_regret_insertion": "cvrp regret lookahead detour second best distance",
    "cvrp_far_first": "cvrp farthest cluster distant customer depot seed route",
    "cvrp_savings": "cvrp savings merge consolidate route distance depot",
    "cvrp_sweep": "cvrp sweep angular sector cluster depot",
    "obp_funsearch_residual_poly": "online bin packing residual polynomial penalty tight fit",
    "obp_eoh_util_sqrt_exp": "online bin packing utilization sqrt exp gap penalty",
    "obp_harmonic": "online bin packing harmonic size class bucket capacity",
}


def _get_code_family(code: str | None) -> set[str]:
    """从生成的代码中提取策略特征关键词，用于判断代码实际体现了哪类策略。

    参数 code 为生成的启发式源码字符串（可能为 None）。
    返回一个特征关键词集合。
    """
    from eoh_rag.rag.features import extract_strategy_features
    return extract_strategy_features(code)


def _card_family(card_ids: list[str]) -> str:
    """根据一组卡片 ID 猜测它们所属的策略族标签。

    通过在拼接后的卡片 ID 文本中匹配关键词（如 nearest、capacity、regret 等），
    返回一个粗粒度的族名；无法识别时返回 "unknown"。
    """
    joined = " ".join(card_ids).lower()
    if "nearest" in joined and "neighbor" in joined:
        return "nearest"
    if "capacity" in joined or "slack" in joined:
        return "capacity"
    if "best_fit" in joined or "first_fit" in joined:
        return "best_fit"
    if "regret" in joined:
        return "regret_mixed"
    if "residual" in joined or "util" in joined:
        return "residual_util"
    return "unknown"


# --- 诊断 ---


@dataclass
class TOCCDecision:
    """承载一次诊断结论的数据类。

    字段含义：
        problem：问题名称（如 tsp_construct / cvrp_construct / bp_online）。
        diagnosis：诊断出的问题类型（见下方注释列出的取值）。
        recommended_cards：建议改用的算子卡片列表。
        recommended_query：建议使用的检索查询词。
        why：给出该诊断的原因说明列表。
        risk：该结论对应的风险提示。
        next_action：建议采取的下一步动作。
    """
    problem: str = ""
    diagnosis: str = ""  # baseline_overlap | wrong_bias | low_diversity | context_truncated | valid_collapse | api_failure | budget_mismatch | no_issue
    recommended_cards: list[str] = field(default_factory=list)
    recommended_query: str = ""
    why: list[str] = field(default_factory=list)
    risk: str = ""
    next_action: str = ""


def diagnose(trace: dict[str, Any]) -> TOCCDecision:
    """对一份运行轨迹字典执行规则诊断，返回诊断结论。

    从 trace 中读取问题名、实验臂、检索选中的卡片与分数、上下文长度、有效候选数、
    种群规模、最优目标值、最优代码、失败原因、运行时长等信息，
    按优先级依次判定属于哪种问题类型（超时/崩溃、无卡片、历史审计命中、
    策略偏置错误、多样性不足、上下文截断等），并填充对应的推荐卡片与查询词。
    未发现任何问题时诊断为 no_issue。
    """
    problem = str(trace.get("problem", ""))
    arm = str(trace.get("arm", ""))
    # 取出本次检索选中的卡片 ID 列表
    selected_ids = [item.get("id", "") for item in trace.get("rag_selected_items", [])]
    scores = trace.get("rag_all_scores", [])
    chars = trace.get("rag_context_chars")
    max_chars = trace.get("rag_max_chars")
    truncated = trace.get("rag_context_truncated")
    valid = trace.get("valid_candidates") or 0
    pop = trace.get("population_size") or 1
    best_obj = trace.get("best_objective")
    best_code = trace.get("best_code")
    failure = trace.get("failure_reason")
    runtime = trace.get("runtime_seconds")

    d = TOCCDecision(problem=problem)

    # --- api_failure：超时或 API 失败 ---
    if failure and "timeout" in str(failure).lower():
        d.diagnosis = "api_failure"
        d.why = ["run timed out or API failure detected"]
        d.risk = "run incomplete; do not compare with completed runs"
        d.next_action = "retry with longer timeout or mark incomplete"
        return d

    # 运行时间过短，通常意味着程序崩溃或立即失败，同样归为 api_failure
    if runtime is not None and runtime < 30:
        d.diagnosis = "api_failure"
        d.why = ["runtime too short, likely crash or immediate failure"]
        d.risk = "invalid run"
        d.next_action = "retry"
        return d

    # --- valid_collapse：有效候选比例过低 ---
    # 有效率 = 有效候选数 / 种群规模，低于 50% 说明生成大量无效解
    valid_rate = valid / max(pop, 1)
    if valid_rate < 0.5 and pop > 1:
        d.diagnosis = "valid_collapse"
        d.why = [f"valid rate {valid_rate:.0%} < 50%", "generation failed or invalid candidates dominate"]
        d.risk = "current card set or context may be too complex"
        d.next_action = "switch to api_only or simpler cards"
        return d

    # --- 只对使用 RAG 卡片的实验臂做卡片级诊断 ---
    if arm not in ("literature_rag", "history_rag", "mixed_rag"):
        d.diagnosis = "no_issue"
        d.why = [f"arm {arm} does not use RAG cards"]
        d.next_action = "no card change needed"
        return d

    # 没有选中任何卡片，无从诊断卡片问题
    if not selected_ids:
        d.diagnosis = "no_issue"
        d.why = ["no RAG cards selected"]
        d.next_action = "run default retrieval first"
        return d

    # --- 历史卡片审计先验判定 ---
    # 载入每张卡片的历史审计结论，并挑出本次选中卡片对应的先验
    prior_decisions = trace.get("card_prior_decisions") or load_card_prior_decisions()
    selected_priors = {
        card_id: prior_decisions.get(card_id)
        for card_id in selected_ids
        if prior_decisions.get(card_id)
    }
    # 被硬性拉黑的卡片：直接判为策略偏置错误并建议替换
    hard_blocked = [
        card_id for card_id, prior in selected_priors.items()
        if str(prior.get("decision", "")) in HARD_BLOCK_DECISIONS
    ]
    if hard_blocked:
        d.diagnosis = "wrong_bias"
        d.why = [f"selected cards are blocked by history-card audit: {hard_blocked}"]
        d.risk = "history prior may inject over-composed or observed-negative operator cards"
        d.next_action = "replace with split or literature cards"
        candidates = TARGETED_CANDIDATE_CARDS.get(problem, [])
        d.recommended_cards = candidates[:2]
        d.recommended_query = f"{problem.replace('_', ' ')} {' '.join(CARD_QUERIES.get(c, c) for c in d.recommended_cards)}".strip()
        return d
    # 被降权或列入观察名单的卡片：判为弱负向，建议人工复核
    deprioritized = [
        card_id for card_id, prior in selected_priors.items()
        if str(prior.get("decision", "")) in DEPRIORITIZED_DECISIONS
    ]
    watchlist = [
        card_id for card_id, prior in selected_priors.items()
        if str(prior.get("decision", "")) in WATCHLIST_DECISIONS
    ]
    if deprioritized:
        d.diagnosis = "weak_negative"
        d.why = [f"selected cards are deprioritized by prior audit: {deprioritized}"]
        if watchlist:
            d.why.append(f"watchlist cards also selected: {watchlist}")
        d.risk = "bounded smoke required; do not treat history prior as default enhancement"
        d.next_action = "manual_review"
        return d

    # --- baseline_overlap：选中的卡片落入基线族，很可能没改变搜索方向 ---
    baseline_set = BASELINE_OVERLAP_CARDS.get(problem, set())
    overlap = set(selected_ids) & baseline_set
    if overlap:
        d.diagnosis = "baseline_overlap"
        d.why = [f"selected cards {sorted(overlap)} overlap with baseline family for {problem}"]
        d.why.append("baseline cards likely do not change search direction")

        candidates = TARGETED_CANDIDATE_CARDS.get(problem, [])
        d.recommended_cards = candidates[:2]
        query_parts = [CARD_QUERIES.get(c, c) for c in candidates[:2] if c in CARD_QUERIES]
        d.recommended_query = f"{problem.replace('_', ' ')} select next {' '.join(query_parts)}".strip()
        d.risk = "targeted cards may overfit; run init-only smoke first"
        d.next_action = "run_init_only"
        return d

    # --- wrong_bias：卡片偏向某策略族，但生成代码里并未体现该策略 ---
    # 卡片族与代码特征错配，说明卡片选择偏离了代码实际走向
    family = _card_family(selected_ids)
    code_family = _get_code_family(best_code)
    if family == "capacity" and "regret" not in code_family and "farthest" not in code_family:
        d.diagnosis = "wrong_bias"
        d.why = [f"selected cards ({family}-biased) do not appear in generated code features"]
        d.why.append("generated code may be dominated by different strategy than cards intended")

        candidates = TARGETED_CANDIDATE_CARDS.get(problem, [])
        d.recommended_cards = candidates[:2]
        query_parts = [CARD_QUERIES.get(c, c) for c in candidates[:2] if c in CARD_QUERIES]
        d.recommended_query = f"{problem.replace('_', ' ')} select next {' '.join(query_parts)}".strip()
        d.risk = "cards may still not match target; validate with diversity check"
        d.next_action = "run_init_only"
        return d

    # --- low_diversity：前 3 名卡片得分过于接近，检索无法区分卡片优劣 ---
    if valid >= 3 and pop == valid and len(scores) >= 3:
        # 兼容两种打分结构：字典 {"score": x} 或序列 [score, ...]
        top_scores = [s["score"] if isinstance(s, dict) else s[0] for s in scores[:3]]
        score_range = max(top_scores) - min(top_scores)
        if score_range < 3:
            d.diagnosis = "low_diversity"
            d.why = [f"top-3 card scores too close (range={score_range})", "retrieval not discriminating between cards"]
            d.next_action = "use targeted query or explicit card_ids to break score ties"
            return d

    # --- context_truncated：上下文可能被截断（优先级较低，放在卡片诊断之后再判） ---
    # 明确标记为截断，或已用字符数逼近上限（>= 95%），都视为可能截断
    if truncated is True or (chars and max_chars and chars >= max_chars * 0.95):
        d.diagnosis = "context_truncated"
        d.why = [f"context {chars}/{max_chars} chars, likely truncated"]
        d.risk = "card content may be incomplete in prompt"
        d.next_action = "reduce top_k or max_chars, or compress cards"
        return d

    # 未命中任何已知失败模式：无需调整卡片
    d.diagnosis = "no_issue"
    d.why = ["no failure mode detected"]
    d.next_action = "maintain current card set"
    return d


# --- 命令行入口 ---


def main() -> None:
    """命令行入口：读取运行摘要 JSON，执行诊断，并将结果打印到标准输出或写入文件。"""
    import argparse

    parser = argparse.ArgumentParser(description="TOCC v1 rule-based operator-card controller")
    parser.add_argument("--trace", required=True, help="Path to official_eoh_run_summary.json")
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {args.trace}")

    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    trace: dict[str, Any] = {}

    # --- 把运行摘要 payload 摊平成 diagnose() 所需的扁平 trace 字典 ---
    problem = payload.get("problem", "")
    arm = payload.get("arm", "")
    rag = payload.get("rag_trace") or {}
    summary = payload.get("run_summary") or {}

    trace["problem"] = problem
    trace["arm"] = arm
    trace["rag_query"] = rag.get("rag_query")
    trace["rag_selected_items"] = rag.get("rag_selected_items", [])
    trace["rag_all_scores"] = rag.get("rag_all_scores", [])
    trace["rag_context_chars"] = rag.get("rag_context_chars")
    trace["rag_max_chars"] = rag.get("rag_max_chars")
    trace["rag_context_truncated"] = rag.get("rag_context_truncated")
    trace["valid_candidates"] = summary.get("valid_candidates")
    trace["population_size"] = summary.get("population_size")
    trace["best_objective"] = summary.get("best_objective")
    trace["best_code"] = summary.get("best_code")
    trace["failure_reason"] = payload.get("failure_reason")
    trace["runtime_seconds"] = payload.get("runtime_seconds")

    decision = diagnose(trace)

    result = {
        "problem": decision.problem,
        "diagnosis": decision.diagnosis,
        "recommended_cards": decision.recommended_cards,
        "recommended_query": decision.recommended_query,
        "why": decision.why,
        "risk": decision.risk,
        "next_action": decision.next_action,
    }

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_text)
    else:
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
