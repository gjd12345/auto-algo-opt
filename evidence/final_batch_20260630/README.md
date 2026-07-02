# Final Batch Evidence — 2026-06-30

## Summary

605 runs across 3 problems using Island Model (gen=8/16, pop=6, shared pool).

| Problem | Runs | Best | Median | Improvement (best) | >5% Rate |
|---------|------|------|--------|-------------------|----------|
| bp_online | 192 | 0.00674 | ~0.036 | +83.1% | 61% |
| tsp_construct | 206 | 6.004 | ~6.22 | +8.5% | 54% |
| cvrp_construct | 207 | 12.356 | ~12.8 | +8.6% | 44% |

## How to Cite

These results are from commit `e1b90b33` (see `commit_hash.txt`).
For paper tables, use `batch_status.json` or `final_best_table.csv`.
For code analysis, see `best_codes/`.

## Key Finding

BP Online best code uses "same-size reservation" strategy (not BestFit).
See `evidence/bp_interpretability/` for full analysis.
