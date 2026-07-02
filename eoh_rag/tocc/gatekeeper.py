"""TOCC Gatekeeper — rule-based proposal validator for V2 agent.

Validates LLM-generated proposals against safety and correctness rules.
Only accepts proposals; never executes runs.
"""

from __future__ import annotations

from typing import Any

import json

from eoh_rag.tocc.controller import (
    BASELINE_OVERLAP_CARDS,
    CARD_QUERIES,
)
from eoh_rag.tocc.card_decisions import (
    DEPRIORITIZED_DECISIONS,
    HARD_BLOCK_DECISIONS,
    WATCHLIST_DECISIONS,
    load_card_prior_decisions,
)
from eoh_rag.tocc.contracts import TOCC_CANDIDATE_POOL_STRATEGY

VALID_DIAGNOSES = {
    "baseline_overlap", "wrong_bias", "low_diversity",
    "context_truncated", "valid_collapse", "api_failure",
    "budget_mismatch", "no_issue",
    "weak_negative", "inconclusive",
}

VALID_ACTIONS = {
    "run_init_only", "retry", "expand_generations",
    "maintain", "manual_review", "run_repeat",
}

PROBLEM_PREFIXES = {
    "tsp_construct": "tsp_",
    "cvrp_construct": "cvrp_",
    "bp_online": "obp_",
}

FORBIDDEN_FIELDS = {
    "pop_size", "generations", "repeats", "max_runs",
    "api_key", "endpoint", "model", "llm_model",
    "output_dir", "shell_command", "shell_cmd", "command",
    "file_write", "file_write_action", "git_operation", "git",
    "env", "environment",
}

# Canonical field names for proposal normalization
FIELD_ALIASES = {
    "candidate_card_ids": "cards",
    "selected_card_ids": "cards",
    "rag_query": "query",
}

MAX_CARDS = 10
MIN_CARDS = 2
MAX_CANDIDATE_CARDS = MAX_CARDS
MIN_CANDIDATE_CARDS = MIN_CARDS
MAX_QUERY_CHARS = 500


def _dedupe_preserve_order(values: Any) -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    deduped: list[str] = []
    duplicates: list[str] = []
    if not values:
        return deduped, duplicates
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        if value in seen:
            duplicates.append(value)
            continue
        seen.add(value)
        deduped.append(value)
    return deduped, duplicates


def _proposal_cards(proposal: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    for source in ("candidate_card_ids", "selected_card_ids", "cards"):
        if proposal.get(source):
            cards, duplicates = _dedupe_preserve_order(proposal.get(source))
            return cards, source, duplicates
    return [], "none", []


def validate_proposal(
    proposal: dict[str, Any],
    *,
    problem: str,
    available_card_ids: list[str] | None = None,
    arm: str = "literature_rag",
    card_prior_decisions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    violations: list[str] = []
    warnings: list[str] = []
    fixed: dict[str, Any] | None = None

    # Normalize field aliases: candidate_card_ids is the canonical candidate pool.
    cards, card_source, duplicate_cards = _proposal_cards(proposal)
    query_raw = proposal.get("query") or proposal.get("rag_query", "")
    proposal = dict(proposal)
    proposal["candidate_card_ids"] = list(cards)
    proposal["cards"] = list(cards)
    proposal["query"] = str(query_raw)

    diagnosis = str(proposal.get("diagnosis", ""))
    query = str(proposal.get("query", ""))
    next_action = str(proposal.get("next_action", ""))
    if duplicate_cards:
        warnings.append(f"R0: deduped duplicate candidate cards: {duplicate_cards}")

    # R1: Card existence
    if available_card_ids:
        unknown = [c for c in cards if c not in available_card_ids]
        if unknown:
            violations.append(f"R1: unknown card IDs: {unknown}")
            return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # R2: Problem prefix match
    prefix = PROBLEM_PREFIXES.get(problem, "")
    if prefix:
        family = problem.split("_", 1)[0]
        allowed_history_prefixes = (f"history_{problem}_", f"history_{family}_")
        mismatched = [
            c for c in cards
            if not (c.startswith(prefix) or c.startswith(allowed_history_prefixes))
        ]
        if mismatched:
            violations.append(f"R2: card IDs do not match problem prefix {prefix!r}: {mismatched}")
            return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # R3: Non-empty cards
    if len(cards) < MIN_CARDS:
        violations.append(f"R3: candidate_card_ids has {len(cards)} cards (min {MIN_CARDS})")
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}
    if len(cards) < 4:
        warnings.append(f"R3: candidate_card_ids has {len(cards)} cards; recommended range is 4-8 when available")

    # R4: Sanity card count
    if len(cards) > MAX_CARDS:
        cards = cards[:MAX_CARDS]
        fixed = dict(proposal)
        fixed["cards"] = cards
        fixed["candidate_card_ids"] = cards
        warnings.append(f"R4: truncated candidate_card_ids from {len(proposal['cards'])} to {MAX_CARDS}")

    # R5: Valid diagnosis
    if diagnosis not in VALID_DIAGNOSES:
        warnings.append(f"R5: unknown diagnosis {diagnosis!r}, set to no_issue")
        diagnosis = "no_issue"
        if fixed is None:
            fixed = dict(proposal)
        fixed["diagnosis"] = "no_issue"

    # R6: Valid next_action
    if next_action not in VALID_ACTIONS:
        warnings.append(f"R6: unknown next_action {next_action!r}, set to manual_review")
        next_action = "manual_review"
        if fixed is None:
            fixed = dict(proposal)
        fixed["next_action"] = "manual_review"

    # R7: Query safety
    if not query or not query.strip():
        violations.append("R7: query is empty")
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}
    if len(query) > MAX_QUERY_CHARS:
        warnings.append(f"R7: query exceeds {MAX_QUERY_CHARS} chars ({len(query)})")

    # R8: Baseline overlap check
    if diagnosis != "baseline_overlap":
        baseline_set = BASELINE_OVERLAP_CARDS.get(problem, set())
        overlap = set(cards) & baseline_set
        if overlap:
            warnings.append(f"R8: cards overlap baseline family {sorted(overlap)} but diagnosis is {diagnosis}")

    # R9: Why/risk presence
    if not proposal.get("why"):
        warnings.append("R9: missing why field")
    if not proposal.get("risk"):
        warnings.append("R9: missing risk field")

    # R10: Strip forbidden fields
    has_forbidden = [k for k in FORBIDDEN_FIELDS if k in proposal]
    if has_forbidden:
        warnings.append(f"R10: stripped forbidden fields: {has_forbidden}")
        if fixed is None:
            fixed = dict(proposal)
        for k in has_forbidden:
            fixed.pop(k, None)

    # R11: Failure diagnosis consistency
    if diagnosis == "api_failure" and next_action != "retry":
        warnings.append("R11: api_failure diagnosis should use retry action")
    if diagnosis == "valid_collapse" and len(cards) > 2:
        warnings.append("R11: valid_collapse suggests simpler cards (<=2)")

    # R12: Card-prior decision gate
    decisions = card_prior_decisions if card_prior_decisions is not None else load_card_prior_decisions()
    why_text = " ".join(str(item) for item in proposal.get("why", []))
    for card_id in cards:
        prior = decisions.get(card_id)
        if not prior:
            continue
        status = str(prior.get("decision", ""))
        if status in HARD_BLOCK_DECISIONS:
            violations.append(f"R12: card {card_id} is marked {status}; split or replace before use")
        elif status in DEPRIORITIZED_DECISIONS:
            explicit = (
                card_id in why_text
                or "deprioritized" in why_text.lower()
                or "审计" in why_text
                or "trace" in why_text.lower()
            )
            if not explicit:
                violations.append(f"R12: card {card_id} is {status}; proposal must include explicit trace-backed why")
        elif status in WATCHLIST_DECISIONS:
            warnings.append(f"R12: card {card_id} is watchlist; run bounded smoke only")
    if violations:
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # Build safe_arm
    effective_cards = fixed["candidate_card_ids"] if fixed else cards
    effective_query = fixed.get("query", query) if fixed else query

    safe_arm = {
        "name": f"agent_proposed_{diagnosis}",
        "runner_arm": arm,
        "context_strategy": TOCC_CANDIDATE_POOL_STRATEGY,
        "rag_query": effective_query,
        "candidate_card_ids": effective_cards,
        "candidate_card_source": card_source,
    }
    accepted = len(violations) == 0

    return {
        "accepted": accepted,
        "violations": violations,
        "warnings": warnings,
        "fixed": fixed,
        "safe_arm": safe_arm if accepted else None,
    }


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="TOCC Gatekeeper — validate LLM proposals")
    parser.add_argument("--proposal", required=True, help="Path to proposal JSON")
    parser.add_argument("--problem", required=True, help="Problem name (tsp_construct, cvrp_construct, bp_online)")
    parser.add_argument("--available-cards", help="Comma-separated list of valid card IDs")
    parser.add_argument("--card-prior-decisions", help="Path to card_prior_decisions.jsonl")
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    args = parser.parse_args()

    proposal = json.loads(open(args.proposal).read())
    available = [c.strip() for c in args.available_cards.split(",")] if args.available_cards else None

    decisions = load_card_prior_decisions(args.card_prior_decisions) if args.card_prior_decisions else None
    result = validate_proposal(
        proposal,
        problem=args.problem,
        available_card_ids=available,
        card_prior_decisions=decisions,
    )

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_text)
    else:
        open(args.output, "w").write(output_text + "\n")

    if not result["accepted"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
