from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eoh_rag.rag.build_corpus import _is_history_card, load_all_corpora
from eoh_rag.rag.prompt_context import format_prompt_context_with_audit
from eoh_rag.rag.reranker import RerankConfig, retrieve_with_rerank, score_corpus_with_rerank
from eoh_rag.rag.retriever import retrieve, score_corpus
from eoh_rag.rag.schemas import CorpusItem


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
}


@dataclass(frozen=True)
class RagContextRequest:
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
    prefixes = OFFICIAL_RAG_PROBLEM_CONFIG[problem]["strategy_prefixes"]
    return item.kind == "algorithm_card" and item.id.startswith(prefixes) and not _is_history_card(item)


def _matches_problem_history(item: CorpusItem, problem: str) -> bool:
    if not _is_history_card(item):
        return False
    if item.id.startswith(f"history_{problem}_"):
        return True
    family = problem.split("_", 1)[0]
    return item.id.startswith(f"history_{family}_") and family in item.tags and "construct" in item.tags


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
    """Return hard-block reasons for a synthesized history card."""
    if not _is_history_card(item):
        return []
    strategy_tags = [
        tag for tag in item.tags
        if tag.lower() not in _NON_STRATEGY_HISTORY_TAGS
    ]
    reasons: list[str] = []
    if len(strategy_tags) > 4:
        reasons.append(f"too_many_strategy_signals:{len(strategy_tags)}")
    do_section = (item.content or "").split("Fallback:", 1)[0]
    do_steps = do_section.count(";") + 1 if "Do:" in do_section else 0
    if do_steps > 5:
        reasons.append(f"too_many_do_steps:{do_steps}")
    return reasons


def history_card_gate_warnings(item: CorpusItem) -> list[str]:
    if not _is_history_card(item):
        return []
    text = f"{item.summary}\n{item.content}".lower()
    warnings: list[str] = []
    if "score" in text and not any(token in text for token in ("maximize", "minimize", "higher is better", "lower is better")):
        warnings.append("score_direction_not_explicit")
    return warnings


def _dedupe_preserve_order(values: list[str] | None) -> list[str]:
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


_CANDIDATE_CARD_SOURCES = {"candidate_card_ids", "selected_card_ids", "cards", "none"}


def resolve_candidate_card_fields(
    *,
    candidate_card_ids: list[str] | None = None,
    selected_card_ids: list[str] | None = None,
    cards: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Resolve legacy public inputs to one canonical candidate allowlist."""
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
    candidates = _dedupe_preserve_order(request.candidate_card_ids)
    if not candidates:
        return "none", []
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
    if not candidate_ids:
        return strategy_pool

    id_set = set(candidate_ids)
    blocked_history_ids = {item["id"] for item in blocked_history_items}
    blocked_selected = [item_id for item_id in candidate_ids if item_id in blocked_history_ids]
    if blocked_selected:
        reason_map = {item["id"]: item["reasons"] for item in blocked_history_items}
        raise ValueError(f"Candidate history cards failed gate: {[(item_id, reason_map[item_id]) for item_id in blocked_selected]}")

    pool_by_id = {item.id: item for item in strategy_pool}
    missing = [item_id for item_id in candidate_ids if item_id not in pool_by_id]
    if missing:
        raise ValueError(f"No matching strategy cards for IDs: {missing}")

    filtered = [pool_by_id[item_id] for item_id in candidate_ids if item_id in pool_by_id]
    if not filtered:
        raise ValueError(f"Candidate allowlist matched no strategy cards: {candidate_ids}")
    return filtered


def build_rag_context(
    project_root: Path,
    request: RagContextRequest,
) -> tuple[str, dict[str, Any]]:
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
    api_ids = set(config["api_ids"])
    global_items = [item for item in corpus if item.kind == "api_constraint" and item.id in api_ids]
    query_text = request.query or str(config["query"])
    literature_pool = [item for item in corpus if _matches_problem_strategy(item, problem)]
    raw_history_pool = [item for item in corpus if _matches_problem_history(item, problem)]
    blocked_history_items = [
        {"id": item.id, "kind": item.kind, "title": item.title, "reasons": history_card_gate_reasons(item)}
        for item in raw_history_pool
        if history_card_gate_reasons(item)
    ]
    history_gate_warnings = [
        {"id": item.id, "kind": item.kind, "title": item.title, "warnings": history_card_gate_warnings(item)}
        for item in raw_history_pool
        if history_card_gate_warnings(item)
    ]
    blocked_history_ids = {item["id"] for item in blocked_history_items}
    history_pool = [item for item in raw_history_pool if item.id not in blocked_history_ids]
    if mode == "literature_rag":
        strategy_pool = literature_pool
    elif mode == "history_rag":
        strategy_pool = history_pool
    else:
        strategy_pool = []
        seen_ids: set[str] = set()
        for item in literature_pool + history_pool:
            if item.id in seen_ids:
                continue
            strategy_pool.append(item)
            seen_ids.add(item.id)

    pool_size_before_filter = len(strategy_pool)
    candidate_source, candidate_ids = _candidate_source(request)
    strategy_pool = _filter_strategy_pool(
        strategy_pool,
        candidate_ids=candidate_ids,
        blocked_history_items=blocked_history_items,
    )
    pool_size_after_filter = len(strategy_pool)

    scored = score_corpus(query_text, strategy_pool)

    llm_rerank_trace = None
    rerank_enabled = bool(request.outcome_summaries or request.population_features)

    if request.rerank_mode == "llm":
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
        retrieved = retrieve_with_rerank(
            query_text, strategy_pool, top_k=top_k,
            outcome_summaries=request.outcome_summaries,
            population_features=request.population_features,
            config=request.rerank_config,
        )
    else:
        retrieved = retrieve(query_text, strategy_pool, top_k=top_k)

    score_by_id = {item.id: score for score, item in scored}
    zero_score_candidate_ids = [
        card_id
        for card_id in dict.fromkeys(candidate_ids)
        if score_by_id.get(card_id) == 0
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
    rerank_scores = (
        score_corpus_with_rerank(
            query_text, strategy_pool,
            outcome_summaries=request.outcome_summaries,
            population_features=request.population_features,
            config=request.rerank_config,
        ) if rerank_enabled else []
    )
    for item in rerank_scores:
        item["selected"] = item["id"] in retrieved_ids
    context, injection_audit = format_prompt_context_with_audit(
        retrieved, max_chars=max_chars, global_items=global_items
    )
    context = context.strip()
    selection_warnings: list[str] = []
    if candidate_ids and pool_size_after_filter <= top_k:
        selection_warnings.append("candidate_pool_size_lte_top_k: rerank has no replacement space")
    if candidate_ids and pool_size_after_filter < 4:
        selection_warnings.append("candidate_pool_size_below_recommended_min: fewer than 4 available candidates")
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
