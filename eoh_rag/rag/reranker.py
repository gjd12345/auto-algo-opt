"""
模块：reranker（检索结果重排序）
功能：在关键词初筛得到候选后，结合"历史效果"与"种群多样性"两类信号，对语料候选做二次打分并重排，选出最终 top-k。
职责：管理重排权重配置（RerankConfig），根据每条语料的历史决策（boost/suppress）放大或抑制分数，并按其与当前种群特征的重叠度施加多样性惩罚。
接口：
    - RerankConfig：重排的可调参数（候选数、放大/抑制倍率、重叠惩罚系数）。
    - retrieve_with_rerank(query, corpus, top_k, *, outcome_summaries, population_features, config) -> list[CorpusItem]：两阶段检索，返回重排后的前 top_k 条语料。
    - score_corpus_with_rerank(query, corpus, *, outcome_summaries, population_features, config) -> list[dict]：对全部语料打分并附带调试信息，用于记录检索轨迹（trace）。
输入：查询串 query、语料列表 corpus（CorpusItem）、历史效果摘要 outcome_summaries、当前种群特征集合 population_features、重排配置 config。
输出：重排后的语料列表；或带打分明细的字典列表。
"""

from __future__ import annotations

from dataclasses import dataclass

from .features import extract_card_features, normalize_strategy_feature
from .schemas import CorpusItem


# 不同语料类型的排序优先级：分数相同时，数字越小越靠前
# algorithm_card（算法卡片）优先于 failure_case（失败案例），再到 api_constraint（接口约束）、code_example（代码示例）
_KIND_PRIORITY = {
    "algorithm_card": 0,
    "failure_case": 1,
    "api_constraint": 2,
    "code_example": 3,
}

@dataclass(frozen=True)
class RerankConfig:
    """重排参数配置（不可变）。

    字段说明：
        candidate_k：初筛阶段保留的候选数量；为 None 时自动按 top_k 推算。
        boost_multiplier：历史决策为 boost 时的分数放大倍率（>1 提升）。
        suppress_multiplier：历史决策为 suppress 时的分数抑制倍率（<1 压低）。
        population_overlap_penalty：与当前种群特征重叠时的多样性惩罚系数，重叠越多、扣分越重。
    """

    candidate_k: int | None = None
    boost_multiplier: float = 1.5
    suppress_multiplier: float = 0.3
    population_overlap_penalty: float = 0.5


def _extract_card_features(item: CorpusItem) -> set[str]:
    """提取一条语料的规范化卡片特征集合（对底层提取函数的薄封装）。"""
    return extract_card_features(item)


def _outcome_decision(summary: object) -> str:
    """从历史效果摘要中取出决策标签。

    摘要既可能是字典也可能是对象，统一读取其 decision 字段；缺失时返回 "neutral"（中性）。
    """
    if isinstance(summary, dict):
        return str(summary.get("decision", "neutral"))
    return str(getattr(summary, "decision", "neutral"))


def retrieve_with_rerank(
    query: str,
    corpus: list[CorpusItem],
    top_k: int = 3,
    *,
    outcome_summaries: dict[str, object] | None = None,
    population_features: set[str] | None = None,
    config: RerankConfig | None = None,
) -> list[CorpusItem]:
    """两阶段检索：先用关键词初筛出前 N 个候选，再结合历史效果与多样性重排，返回最终前 top_k 条。

    参数：
        query：查询串。
        corpus：待检索的语料列表。
        top_k：最终返回的语料条数。
        outcome_summaries：各语料 id 到历史效果摘要的映射，用于 boost/suppress 调整。
        population_features：当前种群已具备的特征集合，用于施加多样性惩罚。
        config：重排参数配置；为 None 时使用默认值。

    返回：重排后的语料列表；若无重排信号则退回纯关键词检索结果。
    """
    from .retriever import retrieve, score_item

    # 语料为空或不需要结果时直接返回空
    if not corpus or top_k <= 0:
        return []

    # 没有任何重排信号（既无历史效果也无种群特征）时，直接返回关键词检索结果
    if not outcome_summaries and not population_features:
        return retrieve(query, corpus, top_k=top_k)

    config = config or RerankConfig()
    # 初筛候选数：默认取 top_k 的 3 倍与 10 中的较大者，且不超过语料总数
    candidate_k = config.candidate_k or min(len(corpus), max(top_k * 3, 10))

    candidates = retrieve(query, corpus, top_k=candidate_k)
    if not candidates:
        return []

    scored: list[tuple[float, CorpusItem]] = []
    # 将种群特征规范化，剔除无法归一的项，得到可比较的特征集合
    normalized_pop = {
        canonical
        for feature in (population_features or set())
        if (canonical := normalize_strategy_feature(feature)) is not None
    }
    for item in candidates:
        base_score = float(score_item(query, item))
        multiplier = 1.0  # 乘性调整因子，初始为 1（不改变基础分）

        # 依据历史决策放大或抑制该语料的分数
        if outcome_summaries and item.id in outcome_summaries:
            decision = _outcome_decision(outcome_summaries[item.id])
            if decision == "boost":
                multiplier *= config.boost_multiplier
            elif decision == "suppress":
                multiplier *= config.suppress_multiplier

        # 多样性惩罚：与当前种群特征重叠越多，扣分越重
        if normalized_pop:
            card_features = extract_card_features(item)
            if card_features:
                overlap = len(card_features & normalized_pop) / len(card_features)
                multiplier *= 1.0 - overlap * config.population_overlap_penalty

        scored.append((base_score * multiplier, item))

    # 排序键：最终分降序 → 类型优先级升序（未知类型排最后）→ id 升序，保证结果稳定
    scored.sort(
        key=lambda pair: (
            -pair[0],
            _KIND_PRIORITY.get(pair[1].kind, 99),
            pair[1].id,
        )
    )
    return [item for _, item in scored[:top_k]]


def score_corpus_with_rerank(
    query: str,
    corpus: list[CorpusItem],
    *,
    outcome_summaries: dict[str, object] | None = None,
    population_features: set[str] | None = None,
    config: RerankConfig | None = None,
) -> list[dict]:
    """对全部语料逐条打分，并返回带调试信息的明细，便于记录检索轨迹（trace）。

    与 retrieve_with_rerank 采用相同的打分逻辑，但不做截断：每条命中的语料都会输出
    基础分、决策标签、种群重叠度、乘性因子与最终分，方便排查为何某条被提升或压低。

    返回：字典列表，按最终分降序、id 升序排列。
    """
    from .retriever import score_item

    config = config or RerankConfig()
    # 规范化种群特征，用于后续计算重叠度
    normalized_pop = {
        canonical
        for feature in (population_features or set())
        if (canonical := normalize_strategy_feature(feature)) is not None
    }

    results = []
    for item in corpus:
        base_score = float(score_item(query, item))
        if base_score <= 0:  # 关键词不命中（基础分非正）的语料直接跳过
            continue
        multiplier = 1.0
        decision = "neutral"
        overlap = 0.0

        # 历史决策：boost 放大、suppress 抑制
        if outcome_summaries and item.id in outcome_summaries:
            decision = _outcome_decision(outcome_summaries[item.id])
            if decision == "boost":
                multiplier *= config.boost_multiplier
            elif decision == "suppress":
                multiplier *= config.suppress_multiplier

        # 与种群特征重叠越多，多样性惩罚越重
        if normalized_pop:
            card_features = extract_card_features(item)
            if card_features:
                overlap = len(card_features & normalized_pop) / len(card_features)
                multiplier *= 1.0 - overlap * config.population_overlap_penalty

        # 记录该条语料的完整打分明细
        results.append({
            "id": item.id,
            "kind": item.kind,
            "base_score": base_score,
            "outcome_decision": decision,
            "population_overlap": round(overlap, 3),
            "multiplier": round(multiplier, 4),
            "final_score": round(base_score * multiplier, 4),
        })

    # 按最终分降序、id 升序排序，保证输出稳定
    results.sort(key=lambda item: (-item["final_score"], item["id"]))
    return results
