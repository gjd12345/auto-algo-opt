"""Card Outcome Memory — evidence layer for RAG card performance tracking.

Records per-card-per-generation results (valid_rate, objective delta, collapse)
so that TOCC controller and future retriever enhancements can use structured
evidence rather than heuristic guesses.

This module is the *evidence layer*. It does NOT replace card_prior_decisions
(the human/rule *decision layer*). Outcome memory records raw facts; whether
to block/boost a card is decided by controller/gatekeeper reading summaries.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CardOutcomeRecord:
    """One row per card per generation injection event."""

    schema_version: str = "card-outcome/v1"

    # Run context
    run_id: str = ""
    trace_path: str = ""
    problem: str = ""
    arm: str = ""
    generation: int = 0
    repeat: int | None = None

    # Card set (solves multi-card attribution)
    card_set_id: str = ""
    selected_card_ids: list[str] = field(default_factory=list)

    # Single card
    card_id: str = ""
    card_rank: int = 0
    card_source: str = ""  # "literature" | "history"
    injection_status: str = ""  # "full" | "truncated" | "omitted"
    injected_chars: int = 0

    # Generation results (shared across card set)
    population_size: int = 0
    valid_candidates: int = 0
    valid_rate: float = 0.0
    best_objective: float | None = None
    pure_baseline: float | None = None
    delta_pct: float | None = None

    # Judgment
    generation_success: bool = False
    objective_success: bool = False
    failure_reason: str | None = None  # "valid_collapse" | "timeout" | "regression" | None
    decision_hint: str = "neutral"  # "positive" | "neutral" | "negative"
    confidence: str = "single_run"  # "single_run" | "repeat"

    timestamp: str = ""


def compute_card_set_id(card_ids: list[str]) -> str:
    """Deterministic hash for a set of card IDs (order-independent)."""
    key = "|".join(sorted(card_ids))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def compute_decision_hint(
    generation_success: bool,
    objective_success: bool,
    valid_rate: float,
    failure_reason: str | None,
) -> str:
    """3-level decision: positive / neutral / negative."""
    if failure_reason in ("valid_collapse", "timeout", "missing_population"):
        return "negative"
    if valid_rate < 0.3:
        return "negative"
    if generation_success and objective_success:
        return "positive"
    return "neutral"


def build_outcome_records(
    run_id: str,
    problem: str,
    generation: int,
    injection_audit: dict[str, Any],
    generation_result: dict[str, Any],
    *,
    arm: str = "",
    repeat: int | None = None,
    trace_path: str = "",
    timestamp: str = "",
) -> list[CardOutcomeRecord]:
    """Build outcome records from a single generation's RAG trace + eval result.

    Parameters
    ----------
    injection_audit : dict
        The audit dict from format_prompt_context_with_audit (rag_injected_items, etc.)
    generation_result : dict
        Must contain: population_size, valid_candidates, best_objective, pure_baseline
    """
    injected_items = injection_audit.get("rag_injected_items", [])
    omitted_items = injection_audit.get("rag_omitted_items", [])

    strategy_items = [e for e in injected_items if e.get("section") == "strategy"]
    strategy_card_ids = [e["id"] for e in strategy_items]
    card_set_id = compute_card_set_id(strategy_card_ids) if strategy_card_ids else ""

    population_size = generation_result.get("population_size", 0)
    valid_candidates = generation_result.get("valid_candidates", 0)
    valid_rate = valid_candidates / max(population_size, 1)
    best_objective = generation_result.get("best_objective")
    pure_baseline = generation_result.get("pure_baseline")
    delta_pct = None
    if best_objective is not None and pure_baseline is not None and pure_baseline != 0:
        delta_pct = round((best_objective - pure_baseline) / abs(pure_baseline) * 100, 2)

    generation_success = generation_result.get("generation_success", valid_rate >= 0.3)
    objective_success = generation_result.get("objective_success", delta_pct is not None and delta_pct < 0)
    failure_reason = generation_result.get("failure_reason")

    decision = compute_decision_hint(generation_success, objective_success, valid_rate, failure_reason)

    records = []
    for rank, entry in enumerate(strategy_items, start=1):
        source = "history" if entry["id"].startswith("history_") else "literature"
        records.append(CardOutcomeRecord(
            run_id=run_id,
            trace_path=trace_path,
            problem=problem,
            arm=arm,
            generation=generation,
            repeat=repeat,
            card_set_id=card_set_id,
            selected_card_ids=strategy_card_ids,
            card_id=entry["id"],
            card_rank=rank,
            card_source=source,
            injection_status=entry.get("status", "full"),
            injected_chars=entry.get("chars", 0),
            population_size=population_size,
            valid_candidates=valid_candidates,
            valid_rate=round(valid_rate, 4),
            best_objective=best_objective,
            pure_baseline=pure_baseline,
            delta_pct=delta_pct,
            generation_success=generation_success,
            objective_success=objective_success,
            failure_reason=failure_reason,
            decision_hint=decision,
            confidence="single_run",
            timestamp=timestamp,
        ))

    for entry in omitted_items:
        source = "history" if entry["id"].startswith("history_") else "literature"
        records.append(CardOutcomeRecord(
            run_id=run_id,
            trace_path=trace_path,
            problem=problem,
            arm=arm,
            generation=generation,
            repeat=repeat,
            card_set_id=card_set_id,
            selected_card_ids=strategy_card_ids,
            card_id=entry["id"],
            card_rank=0,
            card_source=source,
            injection_status="omitted",
            injected_chars=0,
            population_size=population_size,
            valid_candidates=valid_candidates,
            valid_rate=round(valid_rate, 4),
            best_objective=best_objective,
            pure_baseline=pure_baseline,
            delta_pct=delta_pct,
            generation_success=generation_success,
            objective_success=objective_success,
            failure_reason=failure_reason,
            decision_hint=decision,
            confidence="single_run",
            timestamp=timestamp,
        ))

    return records


# ---------------------------------------------------------------------------
# Persistence (JSONL)
# ---------------------------------------------------------------------------

def _outcome_key(record: CardOutcomeRecord) -> tuple:
    """Dedup key: same run + card + generation + injection status = same event."""
    return (record.run_id, record.card_id, record.generation, record.injection_status)


def save_outcomes(records: list[CardOutcomeRecord], path: Path, *, append: bool = True) -> None:
    """Append outcome records to a JSONL file, skipping duplicates.

    Deduplication uses (run_id, card_id, generation, injection_status) so
    re-running the summarizer on the same data does not produce duplicate rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_keys: set[tuple] = set()
    if append and path.exists():
        for existing in load_outcomes(path):
            existing_keys.add(_outcome_key(existing))

    new_records = [r for r in records if _outcome_key(r) not in existing_keys]
    if not new_records:
        return

    with open(path, "a" if append else "w", encoding="utf-8") as f:
        for record in new_records:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_outcomes(path: Path) -> list[CardOutcomeRecord]:
    """Load all outcome records from a JSONL file."""
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            data.pop("schema_version", None)
            records.append(CardOutcomeRecord(**data))
    return records


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class CardOutcomeSummary:
    """Aggregated view of a single card's performance across runs."""

    card_id: str
    total_injections: int = 0
    as_set_member_runs: int = 0
    avg_valid_rate: float = 0.0
    avg_delta_pct: float | None = None
    collapse_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    decision: str = "neutral"  # "boost" | "neutral" | "suppress"


def summarize_card(card_id: str, outcomes: list[CardOutcomeRecord]) -> CardOutcomeSummary:
    """Aggregate outcomes for a single card into a summary."""
    card_records = [r for r in outcomes if r.card_id == card_id and r.injection_status != "omitted"]
    if not card_records:
        return CardOutcomeSummary(card_id=card_id)

    set_ids = {r.card_set_id for r in card_records}
    valid_rates = [r.valid_rate for r in card_records]
    deltas = [r.delta_pct for r in card_records if r.delta_pct is not None]
    collapse_count = sum(1 for r in card_records if r.failure_reason == "valid_collapse")
    positive_count = sum(1 for r in card_records if r.decision_hint == "positive")
    negative_count = sum(1 for r in card_records if r.decision_hint == "negative")

    avg_valid = sum(valid_rates) / len(valid_rates) if valid_rates else 0.0
    avg_delta = sum(deltas) / len(deltas) if deltas else None

    if negative_count >= 3 or collapse_count >= 2:
        decision = "suppress"
    elif positive_count >= 3 and negative_count == 0:
        decision = "boost"
    else:
        decision = "neutral"

    return CardOutcomeSummary(
        card_id=card_id,
        total_injections=len(card_records),
        as_set_member_runs=len(set_ids),
        avg_valid_rate=round(avg_valid, 4),
        avg_delta_pct=round(avg_delta, 2) if avg_delta is not None else None,
        collapse_count=collapse_count,
        positive_count=positive_count,
        negative_count=negative_count,
        decision=decision,
    )


def summarize_all_cards(outcomes: list[CardOutcomeRecord]) -> dict[str, CardOutcomeSummary]:
    """Summarize all cards that have outcome records."""
    card_ids = {r.card_id for r in outcomes if r.injection_status != "omitted"}
    return {cid: summarize_card(cid, outcomes) for cid in sorted(card_ids)}
