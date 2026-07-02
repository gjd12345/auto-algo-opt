# Framework Redesign Proposal — Post-Ablation

> This document proposes directions for the next development cycle based on
> ablation findings. No code changes are implemented here.

## Priority 1: Fix Population Feature Path Mapping

**Problem:** `load_population_features()` cannot find population JSON files in
the batch_runner output structure. D arm is non-functional.

**Proposed fix:**
- In `eoh_single_runner.py`, after the official EoH subprocess completes,
  write a `_population_manifest.json` at the run_out root that records the
  actual path to `results/pops/`
- In `load_population_features()`, first check for this manifest, then
  fall back to the current glob

**Scope:** 3-5 lines in runner + 3-5 lines in features.py. No algorithm change.

**Expected outcome:** D arm activates population features in r2/r3. Can then
measure true population contribution.

## Priority 2: Outcome-Aware RAG for TSP

**Problem:** Outcome rerank helps CVRP (-6%) but is marginal on TSP (-0.8%).
Likely because outcome records are CVRP-heavy.

**Proposed approach:**
1. Run 5-10 TSP-specific iterations (A + C arms)
2. Backfill TSP outcome records from those runs
3. Re-run ablation on TSP with balanced outcome data
4. Compare: does TSP outcome effectiveness improve with better outcome data?

**Not proposed:** Changing outcome scoring formula or multipliers.

## Priority 3: Candidate Pool Expansion

**Problem:** Current pool is 5 literature cards per problem. With top_k=2,
the retriever has minimal selection flexibility.

**Proposed approach:**
1. Include `history_*` cards in candidate pool (filtered by problem prefix)
2. Increase pool to 10-15 cards per problem
3. Keep top_k=2 but let reranker choose from a richer pool
4. Measure if outcome rerank benefit increases with larger pool

**Hypothesis:** Outcome rerank is more valuable when the pool is larger and
contains both good and bad cards to discriminate between.

## Priority 4: Online Outcome Update

**Problem:** Current outcome data is static (backfilled from historical reports).
Running experiments don't update outcomes in real-time.

**Proposed approach:**
1. After each batch_runner run completes:
   - Call `build_outcome_records()` on the generation result
   - Append to `card_outcomes.jsonl`
2. Next run in the sequence sees updated outcomes
3. Over many runs, outcome data becomes self-improving

**Risk:** Feedback loops could amplify early luck (a card that happens to work
once gets boosted, then selected more, creating false evidence). Need decay or
confidence weighting.

## Priority 5: Keyword Search Upgrade

**Problem:** Pure keyword RAG (B arm) adds minimal value. The TF-IDF-like
scoring with strategy features may not be discriminative enough.

**Possible approaches (NOT implementing, just listing):**
- Add semantic similarity via lightweight embeddings (sentence-transformers)
- Add query-dependent card filtering (only cards matching problem domain)
- Replace keyword scoring with BM25
- Add LLM-based reranking (expensive but potentially high quality)

**Note:** Any of these would require significant testing and a separate ablation
round. The current keyword layer is a valid baseline for measuring outcome/population
contribution.

## Not Proposed (Explicitly Out of Scope)

- Changing outcome decision thresholds (suppress/boost/neutral boundaries)
- Changing reranker multiplier values
- Modifying TOCC agent prompts
- Adding new retrieval modalities (embedding, LLM rerank)
- Claiming "superior to EoH" — results are specific to our official EoH wrapper
  with JoyAI-LLM-Pro on Solomon CVRP50/TSP50 instances

## Recommended Next Steps (Priority Order)

1. Fix population path mapping → rerun D arm only (4-6 runs)
2. Backfill TSP outcomes → rerun TSP C arm (3 runs)
3. Expand candidate pool → full 4-arm re-ablation if 1+2 show promise
4. If 1-3 all show improvement: design online outcome loop
5. Paper keywords to search: "retrieval-augmented evolution", "experience-driven optimization", "outcome-aware algorithm configuration"
