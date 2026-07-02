from __future__ import annotations

from dataclasses import dataclass

from .features import extract_card_features, normalize_strategy_feature
from .schemas import CorpusItem


_KIND_PRIORITY = {
    "algorithm_card": 0,
    "failure_case": 1,
    "api_constraint": 2,
    "code_example": 3,
}

@dataclass(frozen=True)
class RerankConfig:
    candidate_k: int | None = None
    boost_multiplier: float = 1.5
    suppress_multiplier: float = 0.3
    population_overlap_penalty: float = 0.5


def _extract_card_features(item: CorpusItem) -> set[str]:
    """Backward-compatible wrapper for the canonical card extractor."""
    return extract_card_features(item)


def _outcome_decision(summary: object) -> str:
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
    """2-stage retrieval: keyword coarse top-N -> outcome/diversity rerank -> top-k."""
    from .retriever import retrieve, score_item

    if not corpus or top_k <= 0:
        return []

    if not outcome_summaries and not population_features:
        return retrieve(query, corpus, top_k=top_k)

    config = config or RerankConfig()
    candidate_k = config.candidate_k or min(len(corpus), max(top_k * 3, 10))

    candidates = retrieve(query, corpus, top_k=candidate_k)
    if not candidates:
        return []

    scored: list[tuple[float, CorpusItem]] = []
    normalized_pop = {
        canonical
        for feature in (population_features or set())
        if (canonical := normalize_strategy_feature(feature)) is not None
    }
    for item in candidates:
        base_score = float(score_item(query, item))
        multiplier = 1.0

        if outcome_summaries and item.id in outcome_summaries:
            decision = _outcome_decision(outcome_summaries[item.id])
            if decision == "boost":
                multiplier *= config.boost_multiplier
            elif decision == "suppress":
                multiplier *= config.suppress_multiplier

        if normalized_pop:
            card_features = extract_card_features(item)
            if card_features:
                overlap = len(card_features & normalized_pop) / len(card_features)
                multiplier *= 1.0 - overlap * config.population_overlap_penalty

        scored.append((base_score * multiplier, item))

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
    """Score all items with rerank debug info for trace recording."""
    from .retriever import score_item

    config = config or RerankConfig()
    normalized_pop = {
        canonical
        for feature in (population_features or set())
        if (canonical := normalize_strategy_feature(feature)) is not None
    }

    results = []
    for item in corpus:
        base_score = float(score_item(query, item))
        if base_score <= 0:
            continue
        multiplier = 1.0
        decision = "neutral"
        overlap = 0.0

        if outcome_summaries and item.id in outcome_summaries:
            decision = _outcome_decision(outcome_summaries[item.id])
            if decision == "boost":
                multiplier *= config.boost_multiplier
            elif decision == "suppress":
                multiplier *= config.suppress_multiplier

        if normalized_pop:
            card_features = extract_card_features(item)
            if card_features:
                overlap = len(card_features & normalized_pop) / len(card_features)
                multiplier *= 1.0 - overlap * config.population_overlap_penalty

        results.append({
            "id": item.id,
            "kind": item.kind,
            "base_score": base_score,
            "outcome_decision": decision,
            "population_overlap": round(overlap, 3),
            "multiplier": round(multiplier, 4),
            "final_score": round(base_score * multiplier, 4),
        })

    results.sort(key=lambda item: (-item["final_score"], item["id"]))
    return results
