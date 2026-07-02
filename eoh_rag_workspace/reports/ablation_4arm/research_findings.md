# Research Findings — RAG Ablation 4-Arm

## Finding 1: Outcome Rerank Has Strong Positive Contribution on CVRP

**Evidence:**
- C arm median 12.715 vs A arm median 13.519 = **-5.9%**
- C arm has lowest std (0.130) across all CVRP arms
- All 3 C repeats beat all 3 A repeats (no overlap)
- 11 outcome summaries loaded, including `cvrp_nearest_capacity` suppress

**Hypothesis:** The outcome suppress on `cvrp_nearest_capacity` (which had repeated valid_collapse in prior runs) prevents the retriever from injecting a card that causes poor generation. The positive boost on `cvrp_regret_insertion` steers context toward proven strategies.

**Next verification needed:** Run C arm with outcome suppress DISABLED to confirm suppress is the key mechanism vs boost.

## Finding 2: Keyword RAG Alone Is Marginal

**Evidence:**
- CVRP: B vs A = -2.9% (marginal)
- TSP: B vs A = +0.9% (no benefit, slightly worse)
- B arm std is comparable to A arm

**Hypothesis:** With 5 candidate cards and top_k=2, the keyword retriever picks reasonable cards but doesn't provide decisive advantage over pure EoH's own exploration. The LLM may already know regret/nearest heuristics without explicit card context.

**Next experiment:** Test with top_k=3 or top_k=4 to see if more context helps, or test with a LARGER candidate pool (include history cards) where keyword selection matters more.

## Finding 3: Population Features Not Activating

**Evidence:**
- `rag_population_feature_count=0` in all 12 D arm runs (both problems)
- D arm r2/r3 should load features from prev_run_dir but don't
- D arm effectively = C arm with different random seeds

**Root cause:** `load_population_features()` in `eoh_rag/rag/features.py` globs for `results/pops/population_generation_*.json` inside the prev_run_dir. But the batch_runner output structure puts the EoH official run outputs in a subdirectory managed by the official EoH code, not at the root of `run_out`. The path mismatch means no population files are found.

**Fix needed (engineering, not algorithm):** Map `run_out` to the actual directory containing `results/pops/`. This is a wiring bug in the batch_runner → eoh_single_runner → official EoH output layout. Should be a 3-5 line fix.

**Next experiment:** After fixing the path mapping, rerun D arm to measure true population contribution.

## Finding 4: Problem-Specific RAG Effectiveness

**Evidence:**
- CVRP: RAG (keyword+outcome) = -6.0% improvement
- TSP: RAG (keyword+outcome) = -0.8% improvement
- CVRP has higher baseline variance, more room for improvement

**Hypothesis:** CVRP is a harder problem (more constraints: capacity, depot, routes) where explicit strategy guidance (regret insertion, farthest-first) provides more value. TSP is simpler and the LLM can discover competitive heuristics through exploration alone.

**Alternative hypothesis:** The outcome records are CVRP-heavy (most historical runs were CVRP). TSP-specific outcome data is sparse, leading to weaker outcome-aware reranking for TSP.

**Next experiment:** Generate TSP-specific outcome data by running several TSP iterations, then re-test C arm.

## Finding 5: Outcome Rerank Reduces Variance on CVRP

**Evidence:**
- A std = 0.230, C std = 0.130 (43% reduction)
- On TSP: A std = 0.137, C std = 0.226 (64% increase)

**Hypothesis:** On CVRP, outcome suppress prevents "bad card" injection that causes variance. On TSP, the outcome data may be insufficiently representative, causing some runs to get boosted cards that are suboptimal for TSP specifically.

## Summary of Hypotheses to Test Next

| # | Hypothesis | Experiment |
|---|-----------|-----------|
| 1 | Outcome suppress is key mechanism | C arm without suppress (set all decisions to "neutral") |
| 2 | Keyword top_k too low | B arm with top_k=3,4 |
| 3 | Population wiring broken | Fix path mapping, rerun D |
| 4 | CVRP-heavy outcome bias | Generate TSP outcomes, retest |
| 5 | Candidate pool too narrow | Include history cards in pool |
