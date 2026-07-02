"""TOCC v1: Rule-based Trace-Conditioned Operator-Card Controller.

Reads an official_eoh_run_summary.json trace and outputs diagnosis +
recommended operator-card set + query.

Does not run LLM. Does not modify files.
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


# --- Problem-specific knowledge ---

BASELINE_OVERLAP_CARDS: dict[str, set[str]] = {
    "tsp_construct": {"tsp_nearest_neighbor", "tsp_nearest_insertion"},
    "cvrp_construct": {"cvrp_nearest_capacity", "cvrp_capacity_slack"},
    "bp_online": {"obp_first_fit", "obp_best_fit", "obp_worst_fit"},
}

TARGETED_CANDIDATE_CARDS: dict[str, list[str]] = {
    "tsp_construct": ["tsp_regret_insertion", "tsp_farthest_insertion", "tsp_two_opt_awareness"],
    "cvrp_construct": ["cvrp_regret_insertion", "cvrp_far_first", "cvrp_savings", "cvrp_sweep"],
    "bp_online": ["obp_funsearch_residual_poly", "obp_eoh_util_sqrt_exp", "obp_harmonic"],
}

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
    """Extract feature keywords from generated code."""
    from eoh_rag.rag.features import extract_strategy_features
    return extract_strategy_features(code)


def _card_family(card_ids: list[str]) -> str:
    """Heuristic family label from card IDs."""
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


# --- Diagnosis ---


@dataclass
class TOCCDecision:
    problem: str = ""
    diagnosis: str = ""  # baseline_overlap | wrong_bias | low_diversity | context_truncated | valid_collapse | api_failure | budget_mismatch | no_issue
    recommended_cards: list[str] = field(default_factory=list)
    recommended_query: str = ""
    why: list[str] = field(default_factory=list)
    risk: str = ""
    next_action: str = ""


def diagnose(trace: dict[str, Any]) -> TOCCDecision:
    """Run rule-based diagnosis on a trace dict."""
    problem = str(trace.get("problem", ""))
    arm = str(trace.get("arm", ""))
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

    # --- api_failure ---
    if failure and "timeout" in str(failure).lower():
        d.diagnosis = "api_failure"
        d.why = ["run timed out or API failure detected"]
        d.risk = "run incomplete; do not compare with completed runs"
        d.next_action = "retry with longer timeout or mark incomplete"
        return d

    if runtime is not None and runtime < 30:
        d.diagnosis = "api_failure"
        d.why = ["runtime too short, likely crash or immediate failure"]
        d.risk = "invalid run"
        d.next_action = "retry"
        return d

    # --- valid_collapse ---
    valid_rate = valid / max(pop, 1)
    if valid_rate < 0.5 and pop > 1:
        d.diagnosis = "valid_collapse"
        d.why = [f"valid rate {valid_rate:.0%} < 50%", "generation failed or invalid candidates dominate"]
        d.risk = "current card set or context may be too complex"
        d.next_action = "switch to api_only or simpler cards"
        return d

    # --- Only run card-level diagnosis for arms that use RAG cards ---
    if arm not in ("literature_rag", "history_rag", "mixed_rag"):
        d.diagnosis = "no_issue"
        d.why = [f"arm {arm} does not use RAG cards"]
        d.next_action = "no card change needed"
        return d

    if not selected_ids:
        d.diagnosis = "no_issue"
        d.why = ["no RAG cards selected"]
        d.next_action = "run default retrieval first"
        return d

    # --- card-prior audit decisions ---
    prior_decisions = trace.get("card_prior_decisions") or load_card_prior_decisions()
    selected_priors = {
        card_id: prior_decisions.get(card_id)
        for card_id in selected_ids
        if prior_decisions.get(card_id)
    }
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

    # --- baseline_overlap ---
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

    # --- wrong_bias: check if selected cards are capacity/biased and obj likely worse ---
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

    # --- low_diversity: unique objective count check ---
    if valid >= 3 and pop == valid and len(scores) >= 3:
        top_scores = [s["score"] if isinstance(s, dict) else s[0] for s in scores[:3]]
        score_range = max(top_scores) - min(top_scores)
        if score_range < 3:
            d.diagnosis = "low_diversity"
            d.why = [f"top-3 card scores too close (range={score_range})", "retrieval not discriminating between cards"]
            d.next_action = "use targeted query or explicit card_ids to break score ties"
            return d

    # --- context_truncated (check after card diagnosis, lower priority) ---
    if truncated is True or (chars and max_chars and chars >= max_chars * 0.95):
        d.diagnosis = "context_truncated"
        d.why = [f"context {chars}/{max_chars} chars, likely truncated"]
        d.risk = "card content may be incomplete in prompt"
        d.next_action = "reduce top_k or max_chars, or compress cards"
        return d

    d.diagnosis = "no_issue"
    d.why = ["no failure mode detected"]
    d.next_action = "maintain current card set"
    return d


# --- CLI ---


def main() -> None:
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

    # --- Flatten official_eoh_run payload into trace ---
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
