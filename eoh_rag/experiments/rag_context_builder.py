"""
模块：rag_context_builder（RAG 上下文构建器）
功能：为组合优化问题（在线装箱 bp_online、TSP、CVRP 等）的启发式进化，从算法卡片语料库里检索出相关内容，拼装成一段可注入到大模型提示词里的上下文文本，并同时产出完整的审计追踪。
职责：
    - 维护每个问题的检索配置（对应的 API 骨架、策略卡前缀、默认查询词）。
    - 从语料库中筛选出「策略卡池」（文献卡 / 历史卡 / 二者混合）与「全局约束卡」。
    - 对合成历史卡做质量门禁（硬拦截 + 软告警），并支持用候选白名单收窄检索范围。
    - 调用检索 / 重排逻辑（关键词检索、特征-结果重排、大模型重排）选出 top_k 条卡片。
    - 把结果格式化成上下文文本，并记录每一步的中间信息用于事后分析。
接口：
    - RagContextRequest：封装单次构建请求的所有参数（问题、模式、查询、top_k 等）。
    - build_rag_context(project_root, request) -> (context_text, trace_dict)：核心入口。
    - build_official_rag_context(...)：面向调用方的便捷封装，把散开的关键字参数收敛为一次请求。
    - history_card_gate_reasons / history_card_gate_warnings：历史卡质量门禁的判定函数。
    - resolve_candidate_card_fields(...)：把多种候选卡入参统一成一份规范白名单。
输入：
    - project_root：语料库所在的项目根目录（Path）。
    - request：一个 RagContextRequest 实例，描述本次检索需求。
输出：
    - 一个二元组：(拼装好的上下文字符串, 审计追踪字典)。
示例：
    ctx, trace = build_official_rag_context(root, "bp_online", "mixed_rag", top_k=5, max_chars=4000)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eoh_rag.rag.build_corpus import _is_history_card, load_all_corpora
from eoh_rag.rag.prompt_context import format_prompt_context_with_audit
from eoh_rag.rag.reranker import RerankConfig, retrieve_with_rerank, score_corpus_with_rerank
from eoh_rag.rag.retriever import retrieve, score_corpus
from eoh_rag.rag.schemas import CorpusItem


# 各支持问题的官方检索配置。键是问题名，值包含三部分：
#   api_ids：该问题对应的「全局约束/接口骨架」卡片 id（无论如何都会注入）。
#   strategy_prefixes：识别该问题策略卡的 id 前缀，用于从语料里筛出候选策略卡。
#   query：当调用方没传自定义查询词时，使用的默认关键词检索文本。
OFFICIAL_RAG_PROBLEM_CONFIG = {
    "bp_online": {
        "api_ids": {"obp_api_skeleton"},
        "strategy_prefixes": ("obp_",),
        "query": (
            "online bin packing score feasible bins residual capacity best fit "
            "harmonic utilization polynomial minimize used bins"
        ),
    },
    "tsp_construct": {
        "api_ids": {"tsp_construct_api_skeleton"},
        "strategy_prefixes": ("tsp_",),
        "query": "tsp construct select next node distance nearest insertion regret route length",
    },
    "cvrp_construct": {
        "api_ids": {"cvrp_construct_api_skeleton"},
        "strategy_prefixes": ("cvrp_",),
        "query": "cvrp construct select next customer distance farthest cluster regret route depot",
    },
    # 派船调度 InsertShips:插入策略卡(nearest/farthest/regret2/savings/solomon_i1)无共同 id 前缀,
    # 但都带 insertships 标签,故用标签选卡(strategy_tags),strategy_prefixes 留空。
    "insertships_go": {
        "api_ids": {"insertships_api_skeleton"},
        "strategy_prefixes": (),
        "strategy_tags": {"insertships"},
        "query": (
            "vehicle routing dynamic ship insertion greedy cheapest cost delta "
            "savings regret farthest nearest capacity feasible route depot"
        ),
    },
}


@dataclass(frozen=True)
class RagContextRequest:
    """一次上下文构建请求的全部参数（不可变数据类）。

    字段说明：
        problem：问题名，须是 OFFICIAL_RAG_PROBLEM_CONFIG 中的键。
        mode：检索模式，取值 literature_rag（只用文献卡）/ history_rag（只用历史卡）/ mixed_rag（两者混合）。
        query：自定义关键词查询；为 None 时回退到该问题的默认 query。
        top_k：最终选出多少条策略卡。
        max_chars：拼装后上下文的字符上限，超出会被截断。
        candidate_card_ids：候选卡白名单（限定只在这些卡里检索）；为 None 表示不限制。
        candidate_card_source：白名单来源标识，仅用于审计记录。
        outcome_summaries：各卡片的历史效果摘要，供重排参考。
        population_features：当前种群已具备的特征集合，供重排参考。
        rerank_config：重排器配置。
        rerank_mode：重排模式，feature_outcome（基于特征与效果）或 llm（大模型重排）。
        rerank_temperature：大模型重排时的采样温度。
    """

    problem: str
    mode: str
    query: str | None
    top_k: int
    max_chars: int
    candidate_card_ids: list[str] | None = None
    candidate_card_source: str = "none"
    outcome_summaries: dict[str, object] | None = None
    population_features: set[str] | None = None
    rerank_config: RerankConfig | None = None
    rerank_mode: str = "feature_outcome"
    rerank_temperature: float = 0.0


def _matches_problem_strategy(item: CorpusItem, problem: str) -> bool:
    # 判断一张卡是否属于该问题的「文献策略卡」：算法卡 + 非历史卡,且 id 命中前缀或标签命中。
    if item.kind != "algorithm_card" or _is_history_card(item):
        return False
    config = OFFICIAL_RAG_PROBLEM_CONFIG[problem]
    prefixes = config["strategy_prefixes"]
    if prefixes and item.id.startswith(prefixes):
        return True
    strategy_tags = config.get("strategy_tags")
    if strategy_tags and (set(item.tags) & strategy_tags):
        return True
    return False


def _matches_problem_history(item: CorpusItem, problem: str) -> bool:
    # 判断一张卡是否属于该问题的「历史策略卡」。
    if not _is_history_card(item):
        return False
    # 精确匹配 history_<problem>_ 前缀的历史卡。
    if item.id.startswith(f"history_{problem}_"):
        return True
    # 否则退到同问题族（如 bp_online 的族名是 bp）：需同时带上族名与 construct 标签才算数。
    family = problem.split("_", 1)[0]
    return item.id.startswith(f"history_{family}_") and family in item.tags and "construct" in item.tags


# 这些标签属于问题/来源类标记，不算「策略信号」，统计策略信号数量时需要排除。
_NON_STRATEGY_HISTORY_TAGS = {
    "bp",
    "obp",
    "tsp",
    "cvrp",
    "construct",
    "online",
    "evolved",
    "history",
}


def history_card_gate_reasons(item: CorpusItem) -> list[str]:
    """返回一张合成历史卡被「硬拦截」的原因列表。

    只对历史卡生效；命中任一规则即视为质量不达标、应排除出候选池。
    返回空列表表示通过门禁。当前规则：策略信号标签超过 4 个、或 Do 步骤超过 5 步。
    """
    if not _is_history_card(item):
        return []
    # 剔除问题/来源类标签后，剩下的才是真正的策略信号标签。
    strategy_tags = [
        tag for tag in item.tags
        if tag.lower() not in _NON_STRATEGY_HISTORY_TAGS
    ]
    reasons: list[str] = []
    if len(strategy_tags) > 4:
        reasons.append(f"too_many_strategy_signals:{len(strategy_tags)}")
    # 只统计 Fallback 之前的 Do 段；以分号分隔的子句数量近似表示步骤数。
    do_section = (item.content or "").split("Fallback:", 1)[0]
    do_steps = do_section.count(";") + 1 if "Do:" in do_section else 0
    if do_steps > 5:
        reasons.append(f"too_many_do_steps:{do_steps}")
    return reasons


def history_card_gate_warnings(item: CorpusItem) -> list[str]:
    """返回一张历史卡的「软告警」列表（不拦截，仅提示潜在质量问题）。

    只对历史卡生效。当前规则：正文提到 score 却未明确说明打分方向
    （最大化 / 最小化 / 越高越好 / 越低越好）时，给出方向不明确的告警。
    """
    if not _is_history_card(item):
        return []
    text = f"{item.summary}\n{item.content}".lower()
    warnings: list[str] = []
    if "score" in text and not any(token in text for token in ("maximize", "minimize", "higher is better", "lower is better")):
        warnings.append("score_direction_not_explicit")
    return warnings


def _dedupe_preserve_order(values: list[str] | None) -> list[str]:
    # 去重并保留首次出现的顺序，同时去掉空白项；输入为空返回空列表。
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


# 候选卡入参的合法来源标识集合，用于校验 candidate_card_source。
_CANDIDATE_CARD_SOURCES = {"candidate_card_ids", "selected_card_ids", "cards", "none"}


def resolve_candidate_card_fields(
    *,
    candidate_card_ids: list[str] | None = None,
    selected_card_ids: list[str] | None = None,
    cards: list[str] | None = None,
) -> tuple[str, list[str]]:
    """将多种候选卡入参统一成一份规范的白名单。

    调用方可能通过 candidate_card_ids、selected_card_ids 或 cards 任一字段传入候选卡；
    本函数按上述优先级取第一个非空来源，去重后返回。
    返回 (来源标识, 卡片 id 列表)；三者都为空时返回 ("none", [])。
    """
    for source, values in (
        ("candidate_card_ids", candidate_card_ids),
        ("selected_card_ids", selected_card_ids),
        ("cards", cards),
    ):
        resolved = _dedupe_preserve_order(values)
        if resolved:
            return source, resolved
    return "none", []


def _candidate_source(request: RagContextRequest) -> tuple[str, list[str]]:
    # 从请求中解析候选卡白名单及其来源标识，并校验来源合法。
    candidates = _dedupe_preserve_order(request.candidate_card_ids)
    if not candidates:
        return "none", []
    # 未指定或标记为 none 时，统一归为 candidate_card_ids 来源。
    source = request.candidate_card_source or "candidate_card_ids"
    if source == "none":
        source = "candidate_card_ids"
    if source not in _CANDIDATE_CARD_SOURCES:
        raise ValueError(f"Unsupported candidate card source: {source}")
    return source, candidates


def _filter_strategy_pool(
    strategy_pool: list[CorpusItem],
    *,
    candidate_ids: list[str],
    blocked_history_items: list[dict[str, Any]],
) -> list[CorpusItem]:
    """按候选白名单收窄策略卡池，并做合法性校验。

    - 白名单为空：原样返回整个池。
    - 白名单命中被硬拦截的历史卡：抛错（不允许选中不达标的卡）。
    - 白名单里有池中不存在的 id：抛错。
    - 正常情况：按白名单顺序过滤出对应卡片；若一张都没匹配上则抛错。
    """
    if not candidate_ids:
        return strategy_pool

    id_set = set(candidate_ids)
    # 若白名单选中的卡里有被门禁硬拦截的历史卡，直接报错并附带原因。
    blocked_history_ids = {item["id"] for item in blocked_history_items}
    blocked_selected = [item_id for item_id in candidate_ids if item_id in blocked_history_ids]
    if blocked_selected:
        reason_map = {item["id"]: item["reasons"] for item in blocked_history_items}
        raise ValueError(f"Candidate history cards failed gate: {[(item_id, reason_map[item_id]) for item_id in blocked_selected]}")

    # 校验白名单中的 id 是否都能在池里找到。
    pool_by_id = {item.id: item for item in strategy_pool}
    missing = [item_id for item_id in candidate_ids if item_id not in pool_by_id]
    if missing:
        raise ValueError(f"No matching strategy cards for IDs: {missing}")

    # 按白名单给定的顺序取出卡片。
    filtered = [pool_by_id[item_id] for item_id in candidate_ids if item_id in pool_by_id]
    if not filtered:
        raise ValueError(f"Candidate allowlist matched no strategy cards: {candidate_ids}")
    return filtered


def build_rag_context(
    project_root: Path,
    request: RagContextRequest,
) -> tuple[str, dict[str, Any]]:
    """核心入口：按请求从语料库检索并拼装出上下文文本与审计追踪。

    主要步骤：
        1. 校验问题名与检索模式合法。
        2. 加载语料，筛出全局约束卡与（文献 / 历史 / 混合）策略卡池。
        3. 对历史卡做门禁：硬拦截项剔除、软告警项记录。
        4. 可选地按候选白名单收窄策略卡池。
        5. 关键词打分后，按 rerank_mode 选择检索 / 重排方式，取出 top_k 条卡片。
        6. 格式化成上下文文本，并汇总各步骤信息写入 trace。

    返回：(上下文字符串, 审计追踪字典)。问题名或模式非法时抛 ValueError。
    """
    problem = request.problem
    mode = request.mode
    top_k = request.top_k
    max_chars = request.max_chars
    if problem not in OFFICIAL_RAG_PROBLEM_CONFIG:
        raise ValueError(f"Unsupported official RAG problem: {problem}")
    if mode not in {"literature_rag", "history_rag", "mixed_rag"}:
        raise ValueError(f"Unsupported official RAG mode: {mode}")

    config = OFFICIAL_RAG_PROBLEM_CONFIG[problem]
    corpus = load_all_corpora(project_root)
    # 全局约束卡：该问题对应的接口骨架，始终注入上下文。
    api_ids = set(config["api_ids"])
    global_items = [item for item in corpus if item.kind == "api_constraint" and item.id in api_ids]
    query_text = request.query or str(config["query"])
    # 分别筛出文献策略卡池与原始历史卡池。
    literature_pool = [item for item in corpus if _matches_problem_strategy(item, problem)]
    raw_history_pool = [item for item in corpus if _matches_problem_history(item, problem)]
    # 历史卡门禁：收集被硬拦截的卡（含原因）。
    blocked_history_items = [
        {"id": item.id, "kind": item.kind, "title": item.title, "reasons": history_card_gate_reasons(item)}
        for item in raw_history_pool
        if history_card_gate_reasons(item)
    ]
    # 历史卡门禁：收集软告警（不剔除，仅记录）。
    history_gate_warnings = [
        {"id": item.id, "kind": item.kind, "title": item.title, "warnings": history_card_gate_warnings(item)}
        for item in raw_history_pool
        if history_card_gate_warnings(item)
    ]
    # 从历史卡池中剔除被硬拦截的卡。
    blocked_history_ids = {item["id"] for item in blocked_history_items}
    history_pool = [item for item in raw_history_pool if item.id not in blocked_history_ids]
    # 按模式确定最终的策略卡池。
    if mode == "literature_rag":
        strategy_pool = literature_pool
    elif mode == "history_rag":
        strategy_pool = history_pool
    else:
        # 混合模式：文献卡在前、历史卡在后，按 id 去重合并。
        strategy_pool = []
        seen_ids: set[str] = set()
        for item in literature_pool + history_pool:
            if item.id in seen_ids:
                continue
            strategy_pool.append(item)
            seen_ids.add(item.id)

    pool_size_before_filter = len(strategy_pool)
    # 若请求带候选白名单，则据此收窄策略卡池。
    candidate_source, candidate_ids = _candidate_source(request)
    strategy_pool = _filter_strategy_pool(
        strategy_pool,
        candidate_ids=candidate_ids,
        blocked_history_items=blocked_history_items,
    )
    pool_size_after_filter = len(strategy_pool)

    # 先做一次关键词打分，供后续零分检测与重排使用。
    scored = score_corpus(query_text, strategy_pool)

    llm_rerank_trace = None
    # 只有当提供了效果摘要或种群特征时，特征-结果重排才有信息可用。
    rerank_enabled = bool(request.outcome_summaries or request.population_features)

    if request.rerank_mode == "llm":
        # 大模型重排模式：交由 llm_rerank 直接给出选中卡片与追踪。
        from eoh_rag.rag.llm_reranker import llm_rerank, LlmRerankTrace
        llm_selected, llm_rerank_trace = llm_rerank(
            query_text,
            strategy_pool,
            top_k=top_k,
            problem=request.problem,
            population_features=request.population_features,
            outcome_summaries=request.outcome_summaries,
            temperature=request.rerank_temperature,
        )
        if llm_selected:
            retrieved = llm_selected
        else:
            # 大模型重排未返回结果时，回退到常规检索 / 特征-结果重排。
            if rerank_enabled:
                retrieved = retrieve_with_rerank(
                    query_text, strategy_pool, top_k=top_k,
                    outcome_summaries=request.outcome_summaries,
                    population_features=request.population_features,
                    config=request.rerank_config,
                )
            else:
                retrieved = retrieve(query_text, strategy_pool, top_k=top_k)
    elif rerank_enabled:
        # 非大模型模式，且有重排信息可用：走特征-结果重排。
        retrieved = retrieve_with_rerank(
            query_text, strategy_pool, top_k=top_k,
            outcome_summaries=request.outcome_summaries,
            population_features=request.population_features,
            config=request.rerank_config,
        )
    else:
        # 无重排信息：退化为纯关键词检索。
        retrieved = retrieve(query_text, strategy_pool, top_k=top_k)

    # 检测「被白名单选中、但关键词得分为 0」的卡，以及其中最终未被取回的卡，用于告警。
    score_by_id = {item.id: score for score, item in scored}
    zero_score_candidate_ids = [
        card_id
        for card_id in dict.fromkeys(candidate_ids)
        if not score_by_id.get(card_id)
    ]
    retrieved_ids = {item.id for item in retrieved}
    dropped_zero_score_candidate_ids = [
        card_id for card_id in zero_score_candidate_ids if card_id not in retrieved_ids
    ]
    zero_score_warnings = (
        ["candidate_cards_dropped_by_zero_keyword_score"]
        if dropped_zero_score_candidate_ids
        else []
    )
    # 若启用重排，额外算出带重排的分数明细，供审计对照。
    rerank_scores = (
        score_corpus_with_rerank(
            query_text, strategy_pool,
            outcome_summaries=request.outcome_summaries,
            population_features=request.population_features,
            config=request.rerank_config,
        ) if rerank_enabled else []
    )
    # 标注每条重排结果是否最终进入了取回集合。
    for item in rerank_scores:
        item["selected"] = item["id"] in retrieved_ids
    # 把取回卡片与全局约束卡格式化成上下文文本，并拿到注入/截断的审计信息。
    context, injection_audit = format_prompt_context_with_audit(
        retrieved, max_chars=max_chars, global_items=global_items
    )
    context = context.strip()
    # 白名单场景下的选择空间告警：候选太少会让重排「无替换余地」或低于建议下限。
    selection_warnings: list[str] = []
    if candidate_ids and pool_size_after_filter <= top_k:
        selection_warnings.append("candidate_pool_size_lte_top_k: rerank has no replacement space")
    if candidate_ids and pool_size_after_filter < 4:
        selection_warnings.append("candidate_pool_size_below_recommended_min: fewer than 4 available candidates")
    # 审计追踪：汇总本次检索的配置、各池规模、门禁结果、打分明细与最终注入情况。
    trace = {
        "rag_mode": mode,
        "rag_query": query_text,
        "rag_top_k": top_k,
        "rag_max_chars": max_chars,
        "rag_corpus_size": len(corpus),
        "rag_strategy_pool_size": len(strategy_pool),
        "rag_candidate_card_ids": candidate_ids,
        "rag_candidate_card_source": candidate_source,
        "rag_candidate_pool_size_before_filter": pool_size_before_filter,
        "rag_candidate_pool_size_after_filter": pool_size_after_filter,
        "rag_selection_space_warning": selection_warnings,
        "candidate_cards_with_zero_keyword_score": zero_score_candidate_ids,
        "candidate_cards_dropped_by_zero_keyword_score": dropped_zero_score_candidate_ids,
        "rag_candidate_zero_score_warning": zero_score_warnings,
        "rag_history_pool_size_before_gate": len(raw_history_pool),
        "rag_history_pool_size_after_gate": len(history_pool),
        "rag_blocked_history_items": blocked_history_items,
        "rag_history_gate_warnings": history_gate_warnings,
        "rag_global_items": [{"id": item.id, "kind": item.kind, "title": item.title} for item in global_items],
        "rag_selected_items": [
            {"id": item.id, "kind": item.kind, "title": item.title} for item in retrieved
        ],
        "rag_all_scores": [
            {"id": item.id, "kind": item.kind, "score": score} for score, item in scored
        ],
        "rag_rerank_scores": rerank_scores,
        "rag_context_chars": len(context),
        "rag_injected_items": injection_audit["rag_injected_items"],
        "rag_omitted_items": injection_audit["rag_omitted_items"],
        "rag_truncated_item_id": injection_audit["rag_truncated_item_id"],
        "rag_context_truncated": injection_audit["rag_context_truncated"],
        "rag_context_sections_chars": injection_audit["rag_context_sections_chars"],
        "rag_rerank_enabled": rerank_enabled if request.rerank_mode != "llm" else False,
        "rag_rerank_mode": request.rerank_mode,
        "rag_population_features": sorted(request.population_features) if request.population_features else [],
        "rag_population_feature_count": len(request.population_features) if request.population_features else 0,
        "rag_outcome_summary_count": len(request.outcome_summaries) if request.outcome_summaries else 0,
    }
    # 大模型重排若发生过，则把其延迟、选中项、推理与回退原因也补进 trace。
    if llm_rerank_trace is not None:
        trace["rag_llm_rerank_latency_ms"] = llm_rerank_trace.latency_ms
        trace["rag_llm_rerank_selected"] = llm_rerank_trace.selected_ids
        trace["rag_llm_rerank_reasoning"] = llm_rerank_trace.reasoning
        trace["rag_llm_rerank_fallback_reason"] = llm_rerank_trace.fallback_reason
    return context, trace


def build_official_rag_context(
    project_root: Path,
    problem: str,
    mode: str,
    top_k: int,
    max_chars: int,
    query: str | None = None,
    selected_card_ids: list[str] | None = None,
    outcome_summaries: dict[str, object] | None = None,
    population_features: set[str] | None = None,
    rerank_config: RerankConfig | None = None,
    candidate_card_ids: list[str] | None = None,
    cards: list[str] | None = None,
    rerank_mode: str = "feature_outcome",
    rerank_temperature: float = 0.0,
) -> tuple[str, dict[str, Any]]:
    """面向调用方的便捷入口：把散开的关键字参数收敛成一次 build_rag_context 调用。

    先用 resolve_candidate_card_fields 把 candidate_card_ids / selected_card_ids / cards
    统一成一份规范白名单，再组装成 RagContextRequest 交给 build_rag_context。
    参数含义与 RagContextRequest 各字段一致；返回同样是 (上下文字符串, 审计追踪字典)。
    """
    candidate_source, effective_candidate_ids = resolve_candidate_card_fields(
        candidate_card_ids=candidate_card_ids,
        selected_card_ids=selected_card_ids,
        cards=cards,
    )
    return build_rag_context(
        project_root,
        RagContextRequest(
            problem=problem,
            mode=mode,
            query=query,
            top_k=top_k,
            max_chars=max_chars,
            candidate_card_ids=effective_candidate_ids or None,
            candidate_card_source=candidate_source,
            outcome_summaries=outcome_summaries,
            population_features=population_features,
            rerank_config=rerank_config,
            rerank_mode=rerank_mode,
            rerank_temperature=rerank_temperature,
        ),
    )
