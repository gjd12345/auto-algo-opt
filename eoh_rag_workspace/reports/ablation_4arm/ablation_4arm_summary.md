# RAG Ablation 4-Arm Experiment Summary

## Experiment Setup

- **Date:** 2026-06-28
- **Branch:** `experiment/rag-ablation-4arm`
- **Problems:** tsp_construct (50 nodes, 8 instances), cvrp_construct (50 customers, 16 instances)
- **Arms:** A_pure / B_keyword / C_keyword_outcome / D_keyword_outcome_pop
- **Config:** gen=4, pop=4, repeats=3, operators=e1,e2,m1,m2
- **Model:** JoyAI-LLM-Pro via api.chatrhino.jd.com
- **Total runs:** 24/24 completed, 0 failures

## Results — CVRP Construct (lower = better)

| Arm | r1 | r2 | r3 | Median | Mean | Std |
|-----|-----|-----|-----|--------|------|-----|
| A_pure | 13.519 | 13.528 | 13.126 | 13.519 | 13.391 | 0.230 |
| B_keyword | 13.499 | 13.033 | 13.126 | 13.126 | 13.219 | 0.243 |
| C_keyword_outcome | **12.715** | **12.632** | **12.886** | **12.715** | **12.744** | 0.130 |
| D_keyword_outcome_pop | 12.618 | 13.033 | 12.930 | 12.930 | 12.860 | 0.216 |

### CVRP Incremental Analysis

| Comparison | Median Δ | % Change | Interpretation |
|------------|----------|----------|----------------|
| B vs A | -0.393 | -2.9% | Keyword RAG marginal improvement |
| C vs B | -0.411 | -3.1% | **Outcome rerank clear benefit** |
| C vs A | -0.804 | **-6.0%** | **Combined keyword+outcome significant** |
| D vs C | +0.215 | +1.7% | Population adds noise, no benefit |

## Results — TSP Construct (lower = better)

| Arm | r1 | r2 | r3 | Median | Mean | Std |
|-----|-----|-----|-----|--------|------|-----|
| A_pure | **6.350** | 6.608 | 6.560 | 6.560 | 6.506 | 0.137 |
| B_keyword | 6.610 | 6.608 | 6.497 | 6.608 | 6.571 | 0.065 |
| C_keyword_outcome | 6.592 | **6.159** | 6.506 | 6.506 | 6.419 | 0.226 |
| D_keyword_outcome_pop | 6.764 | 6.878 | **6.154** | 6.764 | 6.599 | 0.393 |

### TSP Incremental Analysis

| Comparison | Median Δ | % Change | Interpretation |
|------------|----------|----------|----------------|
| B vs A | +0.048 | +0.9% | Keyword RAG no benefit on TSP |
| C vs B | -0.102 | -1.5% | Outcome slight improvement |
| C vs A | -0.054 | -0.8% | Combined marginal on TSP |
| D vs C | +0.258 | +4.0% | Population adds high variance, no median benefit |

## Cross-Problem Findings

### Outcome Rerank (C arm)

| Metric | CVRP | TSP |
|--------|------|-----|
| C best single | 12.632 | 6.159 |
| C median vs A median | **-6.0%** | -0.8% |
| C std vs A std | 0.130 vs 0.230 (lower) | 0.226 vs 0.137 (higher) |
| Outcome summaries loaded | 11 | 11 |

**Key insight:** Outcome rerank has strong, consistent benefit on CVRP but mixed results on TSP. On CVRP it both improves median AND reduces variance. On TSP it improves best-case but increases variance.

### Population Features (D arm)

| Metric | CVRP | TSP |
|--------|------|-----|
| pop_n in all runs | 0 | 0 |
| D median vs C median | +1.7% (worse) | +4.0% (worse) |
| D std vs C std | 0.216 vs 0.130 (higher) | 0.393 vs 0.226 (higher) |

**Key insight:** Population features did NOT activate (`pop_n=0` in all D runs). The `use_prev_run_dir_chain` flag is correctly wired but the prev_run_dir output structure doesn't contain `results/pops/population_generation_*.json` in the expected location. D arm is effectively equivalent to C arm with added noise from longer prompts / different random seeds.

## Verification Checklist

- [x] 24/24 runs completed (status=ok)
- [x] All runs valid_candidates=4 (no valid_collapse)
- [x] C/D outcome_n=11 (outcome loaded correctly)
- [x] B outcome_n=0 (correctly isolated)
- [x] A has no rag_trace (correctly isolated)
- [x] D pop_n=0 (population chain NOT activating — needs investigation)
- [x] No API key committed
- [x] No raw run dirs committed
- [x] All lightweight metrics pushed

## Conclusion

1. **Outcome rerank is the strongest contributor** on CVRP (-6.0% median improvement)
2. **Keyword RAG alone has marginal benefit** (-2.9% CVRP, no benefit TSP)
3. **Population features are NOT activating** — D arm = C arm functionally
4. **Problem-specific:** CVRP benefits much more than TSP from RAG augmentation
5. **Variance:** Outcome rerank reduces variance on CVRP but increases it on TSP
