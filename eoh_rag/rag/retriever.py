from __future__ import annotations

import re
from collections import Counter

from .schemas import CorpusItem


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_KIND_PRIORITY = {
    "algorithm_card": 0,
    "failure_case": 1,
    "api_constraint": 2,
    "code_example": 3,
}


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _weighted_terms(item: CorpusItem) -> Counter[str]:
    terms: Counter[str] = Counter()
    terms.update({token: 3 for token in _tokens(item.title)})
    for tag in item.tags:
        terms.update({token: 3 for token in _tokens(tag)})
    terms.update({token: 2 for token in _tokens(item.summary)})
    for constraint in item.constraints:
        terms.update({token: 2 for token in _tokens(constraint)})
    return terms


def score_item(query: str, item: CorpusItem) -> int:
    query_terms = _tokens(query)
    if not query_terms:
        return 0
    weighted = _weighted_terms(item)
    return sum(weighted.get(term, 0) for term in query_terms)


def score_corpus(query: str, corpus: list[CorpusItem]) -> list[tuple[int, CorpusItem]]:
    scored = [(score_item(query, item), item) for item in corpus]
    scored.sort(
        key=lambda pair: (
            -pair[0],
            _KIND_PRIORITY.get(pair[1].kind, 99),
            pair[1].id,
        )
    )
    return scored


def retrieve(query: str, corpus: list[CorpusItem], top_k: int = 3) -> list[CorpusItem]:
    if not corpus or top_k <= 0:
        return []

    scored = [(score, item) for score, item in score_corpus(query, corpus) if score > 0]
    return [item for _, item in scored[:top_k]]


# Backward-compatible imports while rerank/features move to dedicated modules.
from .features import extract_code_features, load_population_features  # noqa: E402
from .reranker import (  # noqa: E402
    RerankConfig,
    _extract_card_features,
    retrieve_with_rerank,
    score_corpus_with_rerank,
)
