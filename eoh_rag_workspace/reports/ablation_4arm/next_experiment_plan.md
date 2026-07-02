# Next Experiment Plan — Path to Strong 5% Target

## Current Status

- Primary criterion: **ACHIEVED** (CVRP C arm = 5.95%)
- Strong criterion: **NOT MET** (avg = 3.39%, need >=5%)
- Gap: TSP needs improvement from 0.83% to >=5% (or CVRP needs to increase to compensate)

## Root Cause Analysis: Why TSP Underperforms

1. **Outcome data is CVRP-biased:** 68 outcome records from historical runs are predominantly CVRP experiments. TSP-specific outcome evidence is sparse → outcome rerank cannot effectively suppress/boost TSP cards.

2. **TSP is "easier" for pure LLM:** TSP50 with nearest-neighbor/regret is well-known. The LLM can generate competitive heuristics without card guidance, leaving less room for RAG to add value.

3. **Population chain not activating:** D arm should theoretically help TSP more (diverse feature injection to escape local optima), but pop_n=0 means this pathway is dead.

4. **Keyword retrieval slightly hurts TSP:** B arm is -0.73% vs A. The injected card context may be constraining the LLM's creative exploration on TSP specifically.

## Proposed Experiments (Priority Order)

### Experiment 2a: Fix Population Path + Rerun D arm

**Goal:** Determine true population contribution.

**Change:** Fix `load_population_features()` path mapping in batch_runner output structure (engineering fix, not algorithm change).

**Runs:** D arm only, TSP + CVRP, 3 repeats each = 6 runs
**Expected time:** ~1h

**Success if:** D arm with active population achieves >=5% on TSP.

### Experiment 2b: TSP Outcome Backfill + Rerun C arm

**Goal:** Test if outcome effectiveness is data-limited.

**Steps:**
1. Use the 3 TSP A_pure runs + 3 TSP B/C/D runs from this ablation to generate TSP outcome records
2. Backfill to card_outcomes.jsonl (should add ~15-20 TSP-specific records)
3. Rerun TSP C arm with enriched outcome data

**Runs:** C arm, TSP only, 3 repeats = 3 runs
**Expected time:** ~30min

**Success if:** TSP C arm improvement rises from 0.83% to >=3% (suggesting data volume is the bottleneck, and more runs will push past 5%).

### Experiment 2c: Expanded Candidate Pool

**Goal:** Test if 5 cards is too narrow for effective outcome-aware selection.

**Change:** Include top history cards in candidate pool (e.g. `history_cvrp_construct_*` and `history_tsp_construct_*` cards). Pool size → 10-15 per problem.

**Runs:** Full 4-arm ablation with expanded pool, TSP + CVRP, 3 repeats = 24 runs
**Expected time:** ~4h

**Success if:** B arm improves (keyword retrieval benefits from richer pool) AND C arm maintains or improves.

### Experiment 2d: top_k Sensitivity

**Goal:** Test if top_k=2 is suboptimal.

**Change:** Run with top_k=3 and top_k=4.

**Runs:** C arm only, TSP + CVRP, top_k={2,3,4}, 2 repeats = 12 runs
**Expected time:** ~2h

**Success if:** Higher top_k improves TSP without degrading CVRP.

## Decision Logic

```
If 2a succeeds (D arm >=5% on TSP):
  → Strong criterion may be met with D arm as best
  → Ship population feature as key differentiator

If 2b succeeds (TSP C rises to >=3%):
  → Confirm: run 10 more TSP iterations, backfill, retest
  → If then C >=5% on TSP → Strong criterion met

If 2c succeeds (expanded pool helps):
  → Combine with 2b (more outcome data + larger pool)
  → May achieve strong criterion through compounding

If none succeed:
  → Accept Primary-only achievement
  → Outcome rerank is CVRP-specific optimization
  → Pivot to problem-specific card curation for TSP
```

## What NOT To Do (per experiment rules)

- Do NOT change reranker scoring formula
- Do NOT change outcome multiplier values
- Do NOT change suppress/boost thresholds
- Do NOT modify prompts or operators
- Do NOT pick best single run to report
- Do report all medians with all repeats

## Timeline

| Experiment | Dependency | Est. Time | Priority |
|-----------|-----------|-----------|----------|
| 2a (fix pop path) | None | 1h | P0 |
| 2b (TSP outcome backfill) | 2a results optional | 30min | P0 |
| 2c (expanded pool) | After 2a/2b analysis | 4h | P1 |
| 2d (top_k sensitivity) | After 2a/2b analysis | 2h | P2 |

Total if running sequentially: ~8h for complete next round.
