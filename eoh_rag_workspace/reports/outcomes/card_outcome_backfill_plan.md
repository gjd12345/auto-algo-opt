# Card Outcome Backfill Plan

## Goal

Create a cold-start `card_outcomes.jsonl` from archived TOCC/RAG reports so
outcome-aware rerank can be linkage-tested before raw run directories are synced.

This is a summary-derived backfill. It is not a substitute for future raw-trace
outcome records.

## Source Order

### Tier A: `success_funnel.per_run`

Use first when available.

Evidence available:

```text
selected_card_ids
valid_candidates
population_size
best_objective
pure_baseline
generation_success
objective_success
failure_reason
```

Backfill marker:

```text
confidence = summary_backfill_funnel
injection_status = full_assumed
```

### Tier B: `problems[].rows[].cards`

Use when Tier A is absent for the same suite/problem/arm/generation/card set.

Evidence available:

```text
cards
best
valid
pop
arm
problem
generation
```

Backfill marker:

```text
confidence = summary_backfill_problem_row
injection_status = full_assumed
```

Collapse rule:

```text
valid_collapse if observed population_size < expected pop
valid_collapse if valid_candidates < max(2, ceil(0.5 * expected pop))
```

This intentionally marks CVRP `default_rag` seed-only runs as negative evidence
even when their best objective looks superficially acceptable.

### Tier C: Manual outcome notes

Files such as `outcomes/*/best_results.md` are not written to JSONL. They are
human audit notes only.

## Exclusions

- Do not fabricate `rag_injected_items`.
- Do not assign injected character counts.
- Do not claim truncation status from archived summaries.
- Do not treat the backfill as performance validation.

## Execution

Run from repo root:

```powershell
python -m eoh_rag.experiments.reports.backfill_card_outcomes
```

Expected outputs:

```text
eoh_rag_workspace/rag/corpus/card_outcomes.jsonl
eoh_rag_workspace/reports/outcomes/card_outcome_backfill_report.md
```

## Verification

Run:

```powershell
python -m pytest tests/test_backfill_card_outcomes.py tests/test_card_outcomes.py -q
python -m eoh_rag.experiments.reports.backfill_card_outcomes
python -c "from pathlib import Path; from eoh_rag.rag.card_outcomes import load_outcomes, summarize_all_cards; p=Path('eoh_rag_workspace/rag/corpus/card_outcomes.jsonl'); records=load_outcomes(p); summary=summarize_all_cards(records); print({'records': len(records), 'summaries': len(summary)})"
```

Acceptance:

```text
records > 0
summaries > 0
cvrp_nearest_capacity has negative/collapse evidence
cvrp_regret_insertion and cvrp_far_first have positive CVRP evidence
tsp_regret_insertion and tsp_farthest_insertion have TSP evidence
```
