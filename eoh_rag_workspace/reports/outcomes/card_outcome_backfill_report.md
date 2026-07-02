# Card Outcome Backfill Report

This report records the summary-derived cold-start outcome memory generated from archived `summary.json` files.

## Source Tiers

| tier | confidence | use |
|---|---|---|
| A | `summary_backfill_funnel` | Uses `success_funnel.per_run.selected_card_ids`; strongest summary source. |
| B | `summary_backfill_problem_row` | Uses `problems[].rows[].cards`; broader coverage, weaker than raw trace. |
| C | manual notes | `best_results.md` is not written into JSONL; use only as audit notes. |

## Counts

- records: `68`
- cards: `11`
- by_confidence: `{'summary_backfill_funnel': 18, 'summary_backfill_problem_row': 50}`
- by_problem: `{'cvrp_construct': 44, 'tsp_construct': 24}`
- by_decision_hint: `{'negative': 3, 'neutral': 31, 'positive': 34}`

## Card Coverage

| card | records | decision | avg_valid_rate | avg_delta_pct | positive | negative | collapse |
|---|---:|---|---:|---:|---:|---:|---:|
| cvrp_far_first | 19 | boost | 1.0000 | -3.71 | 13 | 0 | 0 |
| cvrp_nearest_capacity | 3 | suppress | 1.0000 | -2.3 | 0 | 3 | 3 |
| cvrp_regret_insertion | 18 | boost | 1.0000 | -4.03 | 13 | 0 | 0 |
| history_cvrp_capacity_feasible_filter | 1 | neutral | 1.0000 | - | 0 | 0 | 0 |
| history_cvrp_construct_capacity_destination_farthest_085049 | 1 | neutral | 1.0000 | - | 0 | 0 | 0 |
| history_cvrp_far_destination_seed | 1 | neutral | 1.0000 | - | 0 | 0 | 0 |
| history_cvrp_remaining_aware_alpha | 1 | neutral | 1.0000 | - | 0 | 0 | 0 |
| tsp_farthest_insertion | 9 | boost | 1.0000 | 5.71 | 3 | 0 | 0 |
| tsp_nearest_insertion | 3 | neutral | 1.0000 | 0.06 | 1 | 0 | 0 |
| tsp_nearest_neighbor | 3 | neutral | 1.0000 | 0.06 | 1 | 0 | 0 |
| tsp_regret_insertion | 9 | boost | 1.0000 | 5.71 | 3 | 0 | 0 |

## Interpretation Warnings

These cards have positive-count evidence but positive average delta; treat them as high-variance exploratory signals, not stable boosts:

| card | records | avg_delta_pct | positive | negative |
|---|---:|---:|---:|---:|
| tsp_farthest_insertion | 9 | 5.71 | 3 | 0 |
| tsp_regret_insertion | 9 | 5.71 | 3 | 0 |

## Caveats

- `injection_status` is `full_assumed`; archived summaries do not preserve `rag_injected_items` or truncation metadata.
- `injected_chars` is `0` for all backfilled rows.
- Treat this as cold-start evidence for rerank smoke tests, not as full-fidelity raw trace evidence.
