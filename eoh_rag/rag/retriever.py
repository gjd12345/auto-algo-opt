"""
模块：retriever（语料检索）
功能：基于关键词的轻量检索器，从知识语料中为查询挑出最相关的若干条目。
职责：把查询和语料条目都拆成词，按加权词频算相关性分数，并按分数、条目类型、id 排序返回。
接口：
    - score_item(query, item) -> int：给单个条目打分。
    - score_corpus(query, corpus) -> list[(int, CorpusItem)]：给整个语料打分并排序。
    - retrieve(query, corpus, top_k=3) -> list[CorpusItem]：返回分数最高的 top_k 条。
输入：查询字符串 query，语料 corpus（CorpusItem 列表，见 .schemas）。
输出：按相关性排序后的条目列表。
示例：
    hits = retrieve("bin packing best fit", corpus, top_k=3)
"""

from __future__ import annotations

import re
from collections import Counter

from .schemas import CorpusItem


# 分词用的正则：匹配连续的字母、数字、下划线，作为一个词
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
# 条目类型的排序优先级：分数相同时，数字越小越靠前
# 顺序为：算法卡片 > 失败案例 > API 约束 > 代码示例
_KIND_PRIORITY = {
    "algorithm_card": 0,
    "failure_case": 1,
    "api_constraint": 2,
    "code_example": 3,
}


def _tokens(text: str) -> list[str]:
    """把一段文本拆成小写词列表（按字母/数字/下划线切分）。"""
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _weighted_terms(item: CorpusItem) -> Counter[str]:
    """把一个条目展开成"词 -> 权重"的计数表。

    不同字段的词权重不同，越核心的字段权重越高：
    标题、标签权重 3；摘要、约束权重 2。
    同一个词在多处出现时权重累加。
    """
    terms: Counter[str] = Counter()
    # 标题：权重 3
    terms.update({token: 3 for token in _tokens(item.title)})
    # 每个标签：权重 3
    for tag in item.tags:
        terms.update({token: 3 for token in _tokens(tag)})
    # 摘要：权重 2
    terms.update({token: 2 for token in _tokens(item.summary)})
    # 每条约束：权重 2
    for constraint in item.constraints:
        terms.update({token: 2 for token in _tokens(constraint)})
    return terms


def score_item(query: str, item: CorpusItem) -> int:
    """计算查询与单个条目的相关性分数。

    参数：
        query：查询字符串。
        item：待打分的语料条目。
    返回：把查询中每个词在条目里的权重相加得到的整数分数；查询为空时返回 0。
    """
    query_terms = _tokens(query)
    if not query_terms:
        return 0
    weighted = _weighted_terms(item)
    # 把查询里每个词命中的权重累加起来
    return sum(weighted.get(term, 0) for term in query_terms)


def score_corpus(query: str, corpus: list[CorpusItem]) -> list[tuple[int, CorpusItem]]:
    """给整个语料打分并排序。

    返回 (分数, 条目) 列表，排序规则依次为：
    分数从高到低 -> 条目类型优先级从小到大 -> id 升序（保证结果稳定）。
    """
    scored = [(score_item(query, item), item) for item in corpus]
    scored.sort(
        key=lambda pair: (
            -pair[0],  # 分数高的排前面
            _KIND_PRIORITY.get(pair[1].kind, 99),  # 未知类型排到最后
            pair[1].id,  # 同分同类型按 id 保证顺序确定
        )
    )
    return scored


def retrieve(query: str, corpus: list[CorpusItem], top_k: int = 3) -> list[CorpusItem]:
    """检索与查询最相关的 top_k 个条目。

    参数：
        query：查询字符串。
        corpus：待检索的语料条目列表。
        top_k：最多返回的条目数量，默认 3。
    返回：按相关性排序、且分数大于 0 的前 top_k 个条目；语料为空或 top_k<=0 时返回空列表。
    """
    if not corpus or top_k <= 0:
        return []

    # 只保留分数大于 0 的条目（真正命中查询词的）
    scored = [(score, item) for score, item in score_corpus(query, corpus) if score > 0]
    return [item for _, item in scored[:top_k]]


# 从其他专门模块引入 rerank / 特征提取相关能力，供外部统一从本模块使用。
from .features import extract_code_features, load_population_features  # noqa: E402
from .reranker import (  # noqa: E402
    RerankConfig,
    _extract_card_features,
    retrieve_with_rerank,
    score_corpus_with_rerank,
)
