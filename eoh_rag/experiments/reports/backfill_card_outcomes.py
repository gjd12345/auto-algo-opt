"""Backfill card outcome memory from archived summary.json reports.

This is a cold-start bridge for outcome-aware reranking. It uses archived
auto_experiment_reports summaries when raw per-run directories are unavailable.
The output follows CardOutcomeRecord so existing load/summarize code can read it.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eoh_rag.rag.card_outcomes import (
    CardOutcomeRecord,
    compute_card_set_id,
    compute_decision_hint,
    save_outcomes,
    summarize_all_cards,
)


BACKFILL_TIMESTAMP = "2026-06-28T00:00:00Z"
TIER_FUNNEL = "summary_backfill_funnel"
TIER_PROBLEM_ROW = "summary_backfill_problem_row"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _card_source(card_id: str) -> str:
    return "history" if card_id.startswith("history_") else "literature"


def _parse_valid(value: str | None) -> tuple[int, int]:
    if not value or "/" not in value:
        return 0, 0
    left, right = value.split("/", 1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return 0, 0


def _repeat_from_id(run_id: str) -> int | None:
    marker = ":r"
    if marker not in run_id:
        return None
    try:
        return int(run_id.rsplit(marker, 1)[1])
    except ValueError:
        return None


def _delta_pct(best: float | None, baseline: float | None) -> float | None:
    if best is None or baseline in (None, 0):
        return None
    return round((best - baseline) / abs(baseline) * 100, 2)


def _objective_success(best: float | None, baseline: float | None) -> bool:
    return best is not None and baseline is not None and best < baseline


def _collapse_failure(
    *,
    valid_candidates: int,
    population_size: int,
    expected_pop: int | None,
    failure_reason: str | None,
) -> str | None:
    if failure_reason:
        return failure_reason
    if expected_pop and population_size < expected_pop:
        return "valid_collapse"
    if expected_pop and valid_candidates < max(2, math.ceil(0.5 * expected_pop)):
        return "valid_collapse"
    return None


def _record(
    *,
    suite: str,
    source_path: Path,
    confidence: str,
    run_id: str,
    problem: str,
    arm: str,
    generation: int,
    repeat: int | None,
    cards: list[str],
    card_id: str,
    card_rank: int,
    population_size: int,
    valid_candidates: int,
    best_objective: float | None,
    pure_baseline: float | None,
    generation_success: bool,
    objective_success: bool,
    failure_reason: str | None,
) -> CardOutcomeRecord:
    valid_rate = valid_candidates / max(population_size, 1)
    decision = compute_decision_hint(
        generation_success=generation_success,
        objective_success=objective_success,
        valid_rate=valid_rate,
        failure_reason=failure_reason,
    )
    return CardOutcomeRecord(
        run_id=run_id,
        trace_path=f"{source_path.as_posix()}#{confidence}",
        problem=problem,
        arm=arm,
        generation=generation,
        repeat=repeat,
        card_set_id=compute_card_set_id(cards),
        selected_card_ids=list(cards),
        card_id=card_id,
        card_rank=card_rank,
        card_source=_card_source(card_id),
        injection_status="full_assumed",
        injected_chars=0,
        population_size=population_size,
        valid_candidates=valid_candidates,
        valid_rate=round(valid_rate, 4),
        best_objective=best_objective,
        pure_baseline=pure_baseline,
        delta_pct=_delta_pct(best_objective, pure_baseline),
        generation_success=generation_success,
        objective_success=objective_success,
        failure_reason=failure_reason,
        decision_hint=decision,
        confidence=confidence,
        timestamp=BACKFILL_TIMESTAMP,
    )


def _suite_problem_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for problem, problem_rows in (summary.get("problems") or {}).items():
        for row_index, row in enumerate(problem_rows, start=1):
            cards = [card for card in (row.get("cards") or []) if card]
            if not cards:
                continue
            rows.append({"problem": problem, "row_index": row_index, **row, "cards": cards})
    return rows


def _problem_baselines(summary: dict[str, Any]) -> dict[str, float]:
    baselines: dict[str, float] = {}
    for problem, rows in (summary.get("problems") or {}).items():
        pure = [
            row.get("best")
            for row in rows
            if row.get("arm") == "pure_eoh" and isinstance(row.get("best"), (int, float))
        ]
        if pure:
            baselines[problem] = sum(pure) / len(pure)
    for problem, baseline in ((summary.get("success_funnel") or {}).get("pure_baselines") or {}).items():
        if isinstance(baseline, (int, float)):
            baselines[problem] = baseline
    return baselines


def _successful_problem_row_cards(summary: dict[str, Any]) -> dict[str, set[str]]:
    successful: dict[str, set[str]] = {}
    baselines = _problem_baselines(summary)
    for row in _suite_problem_rows(summary):
        problem = str(row.get("problem") or "")
        valid_candidates, observed_population = _parse_valid(row.get("valid"))
        expected_pop = row.get("pop") if isinstance(row.get("pop"), int) else None
        population_size = observed_population or expected_pop or valid_candidates
        failure_reason = _collapse_failure(
            valid_candidates=valid_candidates,
            population_size=population_size,
            expected_pop=expected_pop,
            failure_reason=row.get("failure_reason"),
        )
        best = row.get("best")
        baseline = baselines.get(problem)
        if failure_reason is None and _objective_success(best, baseline):
            successful.setdefault(problem, set()).update(row.get("cards") or [])
    return successful


def _funnel_records(summary_path: Path, summary: dict[str, Any]) -> tuple[list[CardOutcomeRecord], set[tuple[str, str, int, tuple[str, ...]]]]:
    suite = summary_path.parent.name
    records: list[CardOutcomeRecord] = []
    covered_groups: set[tuple[str, str, int, tuple[str, ...]]] = set()
    for row in (summary.get("success_funnel") or {}).get("per_run") or []:
        cards = [card for card in (row.get("selected_card_ids") or []) if card]
        if not cards:
            continue
        population_size = int(row.get("population_size") or 0)
        valid_candidates = int(row.get("valid_candidates") or 0)
        if population_size <= 0:
            continue
        problem = str(row.get("problem") or "")
        arm = str(row.get("arm") or "")
        generation = int(row.get("gen") or 0)
        run_id = str(row.get("best_code_record_id") or f"{problem}:{arm}:g{generation}:funnel")
        baseline = row.get("pure_baseline")
        best = row.get("best_objective")
        failure_reason = row.get("failure_reason")
        generation_success = bool(row.get("generation_success"))
        objective_success = bool(row.get("objective_success")) if row.get("objective_success") is not None else _objective_success(best, baseline)
        group_key = (problem, arm, generation, tuple(cards))
        covered_groups.add(group_key)
        for rank, card_id in enumerate(cards, start=1):
            records.append(_record(
                suite=suite,
                source_path=summary_path,
                confidence=TIER_FUNNEL,
                run_id=run_id,
                problem=problem,
                arm=arm,
                generation=generation,
                repeat=_repeat_from_id(run_id),
                cards=cards,
                card_id=card_id,
                card_rank=rank,
                population_size=population_size,
                valid_candidates=valid_candidates,
                best_objective=best,
                pure_baseline=baseline,
                generation_success=generation_success,
                objective_success=objective_success,
                failure_reason=failure_reason,
            ))
    return records, covered_groups


def _problem_row_records(
    summary_path: Path,
    summary: dict[str, Any],
    covered_funnel_groups: set[tuple[str, str, int, tuple[str, ...]]],
) -> list[CardOutcomeRecord]:
    suite = summary_path.parent.name
    baselines = _problem_baselines(summary)
    successful_cards = _successful_problem_row_cards(summary)
    rows = _suite_problem_rows(summary)
    counters: Counter[tuple[str, str, int, tuple[str, ...]]] = Counter()
    records: list[CardOutcomeRecord] = []
    for row in rows:
        problem = str(row.get("problem") or "")
        arm = str(row.get("arm") or "")
        generation = int(row.get("gen") or 0)
        cards = list(row.get("cards") or [])
        group_key = (problem, arm, generation, tuple(cards))
        if group_key in covered_funnel_groups:
            continue
        counters[group_key] += 1
        repeat = counters[group_key]
        valid_candidates, observed_population = _parse_valid(row.get("valid"))
        expected_pop = row.get("pop") if isinstance(row.get("pop"), int) else None
        population_size = observed_population or expected_pop or valid_candidates
        best = row.get("best")
        baseline = baselines.get(problem)
        row_failure_reason = _collapse_failure(
            valid_candidates=valid_candidates,
            population_size=population_size,
            expected_pop=expected_pop,
            failure_reason=row.get("failure_reason"),
        )
        row_generation_success = row_failure_reason != "valid_collapse" and (
            valid_candidates >= max(2, math.ceil(0.5 * (expected_pop or population_size or 1)))
        )
        objective_success = _objective_success(best, baseline)
        run_id = f"{problem}:{arm}:g{generation}:r{repeat}:summary_backfill"
        for rank, card_id in enumerate(cards, start=1):
            # Multi-card attribution is ambiguous. If a card also appears in a
            # successful same-problem combination, do not let a collapsed set
            # alone suppress it during cold-start backfill.
            failure_reason = row_failure_reason
            generation_success = row_generation_success
            if row_failure_reason == "valid_collapse" and card_id in successful_cards.get(problem, set()):
                failure_reason = None
                generation_success = False
            records.append(_record(
                suite=suite,
                source_path=summary_path,
                confidence=TIER_PROBLEM_ROW,
                run_id=run_id,
                problem=problem,
                arm=arm,
                generation=generation,
                repeat=repeat,
                cards=cards,
                card_id=card_id,
                card_rank=rank,
                population_size=population_size,
                valid_candidates=valid_candidates,
                best_objective=best,
                pure_baseline=baseline,
                generation_success=generation_success,
                objective_success=objective_success,
                failure_reason=failure_reason,
            ))
    return records


def build_backfill_records(reports_dir: Path) -> list[CardOutcomeRecord]:
    records: list[CardOutcomeRecord] = []
    for summary_path in sorted(reports_dir.glob("*/summary.json")):
        summary = _load_json(summary_path)
        funnel_records, covered_groups = _funnel_records(summary_path, summary)
        records.extend(funnel_records)
        records.extend(_problem_row_records(summary_path, summary, covered_groups))
    records.sort(key=lambda r: (r.problem, r.arm, r.generation, r.repeat or 0, r.card_rank, r.card_id, r.confidence))
    return records


def summarize_backfill(records: list[CardOutcomeRecord]) -> dict[str, Any]:
    by_confidence = Counter(r.confidence for r in records)
    by_problem = Counter(r.problem for r in records)
    by_card = Counter(r.card_id for r in records)
    by_decision = Counter(r.decision_hint for r in records)
    summaries = summarize_all_cards(records)
    return {
        "records": len(records),
        "cards": len(summaries),
        "by_confidence": dict(sorted(by_confidence.items())),
        "by_problem": dict(sorted(by_problem.items())),
        "by_decision_hint": dict(sorted(by_decision.items())),
        "by_card": dict(by_card.most_common()),
        "card_decisions": {
            card_id: asdict(summary)
            for card_id, summary in summaries.items()
        },
    }


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Card Outcome Backfill Report",
        "",
        "This report records the summary-derived cold-start outcome memory generated from archived `summary.json` files.",
        "",
        "## Source Tiers",
        "",
        "| tier | confidence | use |",
        "|---|---|---|",
        "| A | `summary_backfill_funnel` | Uses `success_funnel.per_run.selected_card_ids`; strongest summary source. |",
        "| B | `summary_backfill_problem_row` | Uses `problems[].rows[].cards`; broader coverage, weaker than raw trace. |",
        "| C | manual notes | `best_results.md` is not written into JSONL; use only as audit notes. |",
        "",
        "## Counts",
        "",
        f"- records: `{summary['records']}`",
        f"- cards: `{summary['cards']}`",
        f"- by_confidence: `{summary['by_confidence']}`",
        f"- by_problem: `{summary['by_problem']}`",
        f"- by_decision_hint: `{summary['by_decision_hint']}`",
        "",
        "## Card Coverage",
        "",
        "| card | records | decision | avg_valid_rate | avg_delta_pct | positive | negative | collapse |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for card_id, card_summary in summary["card_decisions"].items():
        lines.append(
            "| {card} | {total} | {decision} | {valid:.4f} | {delta} | {pos} | {neg} | {collapse} |".format(
                card=card_id,
                total=card_summary["total_injections"],
                decision=card_summary["decision"],
                valid=card_summary["avg_valid_rate"],
                delta="-" if card_summary["avg_delta_pct"] is None else card_summary["avg_delta_pct"],
                pos=card_summary["positive_count"],
                neg=card_summary["negative_count"],
                collapse=card_summary["collapse_count"],
            )
        )
    unstable_boosts = [
        (card_id, card_summary)
        for card_id, card_summary in summary["card_decisions"].items()
        if card_summary["decision"] == "boost"
        and card_summary["avg_delta_pct"] is not None
        and card_summary["avg_delta_pct"] > 0
    ]
    if unstable_boosts:
        lines.extend([
            "",
            "## Interpretation Warnings",
            "",
            "These cards have positive-count evidence but positive average delta; treat them as high-variance exploratory signals, not stable boosts:",
            "",
            "| card | records | avg_delta_pct | positive | negative |",
            "|---|---:|---:|---:|---:|",
        ])
        for card_id, card_summary in unstable_boosts:
            lines.append(
                "| {card} | {total} | {delta} | {pos} | {neg} |".format(
                    card=card_id,
                    total=card_summary["total_injections"],
                    delta=card_summary["avg_delta_pct"],
                    pos=card_summary["positive_count"],
                    neg=card_summary["negative_count"],
                )
            )
    lines.extend([
        "",
        "## Caveats",
        "",
        "- `injection_status` is `full_assumed`; archived summaries do not preserve `rag_injected_items` or truncation metadata.",
        "- `injected_chars` is `0` for all backfilled rows.",
        "- Treat this as cold-start evidence for rerank smoke tests, not as full-fidelity raw trace evidence.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill card_outcomes.jsonl from archived summary.json reports")
    parser.add_argument("--reports-dir", default="eoh_rag_workspace/reports/auto_experiment_reports")
    parser.add_argument("--output", default="eoh_rag_workspace/rag/corpus/card_outcomes.jsonl")
    parser.add_argument("--report", default="eoh_rag_workspace/reports/outcomes/card_outcome_backfill_report.md")
    args = parser.parse_args()

    records = build_backfill_records(Path(args.reports_dir))
    save_outcomes(records, Path(args.output), append=False)
    summary = summarize_backfill(records)
    write_report(Path(args.report), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
