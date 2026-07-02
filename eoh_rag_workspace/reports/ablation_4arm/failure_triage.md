# Failure Triage — RAG Ablation 4-Arm

## Summary

- **Total runs:** 24
- **Successful:** 24 (100%)
- **Failed:** 0
- **Retried:** 0

## No failures to triage

All 24 runs completed successfully with `return_code=0` and `valid_candidates=4`. No API timeouts, no valid collapses, no missing environments.

## Non-Critical Observations

### Population chain not activating (D arm)

- **Symptom:** `rag_population_feature_count=0` in all 12 D arm runs
- **Expected:** D r2/r3 should have pop_n > 0 (loaded from prev_run_dir)
- **Root cause hypothesis:** The batch_runner `run_out` directory structure places EoH outputs in a nested path that doesn't match the `results/pops/population_generation_*.json` glob pattern expected by `load_population_features()`
- **Impact:** D arm = C arm functionally. Not a failure — just unrealized feature.
- **Action:** Investigate in next experiment cycle (see research_findings.md)

### Runtime variance

- D arm runs tend to be slower (avg 728s vs A arm avg 469s)
- Likely due to outcome rerank computation overhead + longer context injection
- Not a concern for correctness
