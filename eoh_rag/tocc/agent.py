"""TOCC V2 Agent — LLM proposer for operator-card selection.

Reads run traces, calls LLM to propose next card set + query.
LLM only proposes; gatekeeper enforces.
"""

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
    """Extract trace fields from official_eoh_run_summary.json."""
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    rag = payload.get("rag_trace") or {}
    run_sum = payload.get("run_summary") or {}

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
        "available_cards": TARGETED_CANDIDATE_CARDS.get(payload.get("problem", ""), []) +
                           list(BASELINE_OVERLAP_CARDS.get(payload.get("problem", ""), set())),
        "baseline_cards": list(BASELINE_OVERLAP_CARDS.get(payload.get("problem", ""), set())),
        "pure_eoh_best": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("pure"),
        "historical_best": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("targeted"),
        "historical_best_cards": _BASELINE_OBJECTIVES.get(payload.get("problem", ""), {}).get("cards", []),
    }


# Known best objectives for comparative diagnosis
_BASELINE_OBJECTIVES = {
    "tsp_construct": {"pure": 6.839, "targeted": 6.217, "cards": ["tsp_regret_insertion", "tsp_farthest_insertion"]},
    "cvrp_construct": {"pure": 13.207, "targeted": 12.821, "cards": ["cvrp_regret_insertion", "cvrp_far_first"]},
}


def _build_user_prompt(trace: dict[str, Any]) -> str:
    """Build user prompt with trace data."""
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
    """Propose next card set from a run trace.

    Returns: {"proposal": {...}, "gatekeeper": {...}, "error": None}
    """
    from eoh_rag.llm.client import chat_completion

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

    # Handle case where LLM wraps JSON in markdown code block
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    try:
        proposal = json.loads(content.strip())
    except json.JSONDecodeError as e:
        return {"proposal": None, "gatekeeper": None, "error": f"JSON parse failed: {e}"}

    return {"proposal": proposal, "gatekeeper": None, "error": None}
