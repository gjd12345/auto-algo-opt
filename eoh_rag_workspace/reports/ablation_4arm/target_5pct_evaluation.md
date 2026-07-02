# RAG Ablation 4-Arm — 5% Target Evaluation

## Metric Definition

```
improvement_pct = (pure_eoh_median - method_median) / abs(pure_eoh_median) * 100
```

All problems minimize objective. improvement_pct >= 5.0% = target met.

---

## CVRP Construct

| Arm | r1 | r2 | r3 | Median | Mean | Std |
|-----|-----|-----|-----|--------|------|-----|
| A_pure | 13.126 | 13.519 | 13.528 | 13.519 | 13.391 | 0.230 |
| B_keyword | 13.033 | 13.126 | 13.499 | 13.126 | 13.219 | 0.247 |
| C_keyword_outcome | 12.632 | 12.714 | 12.886 | **12.715** | **12.744** | 0.130 |
| D_keyword_outcome_pop | 12.618 | 12.930 | 13.033 | 12.930 | 12.860 | 0.216 |

### CVRP improvement_pct (vs A_pure median=13.519)

| Comparison | improvement_pct | >=5%? |
|------------|----------------|-------|
| B vs A | 2.91% | no |
| **C vs A** | **5.95%** | **YES** |
| D vs A | 4.36% | no |

### CVRP Incremental

| Comparison | Δ% |
|------------|-----|
| C vs B | +3.14% |
| D vs C | -1.70% |

---

## TSP Construct

| Arm | r1 | r2 | r3 | Median | Mean | Std |
|-----|-----|-----|-----|--------|------|-----|
| A_pure | 6.350 | 6.560 | 6.608 | 6.560 | 6.506 | 0.137 |
| B_keyword | 6.497 | 6.608 | 6.610 | 6.608 | 6.572 | 0.065 |
| C_keyword_outcome | 6.159 | 6.506 | 6.592 | 6.506 | 6.419 | 0.229 |
| D_keyword_outcome_pop | 6.154 | 6.764 | 6.878 | 6.764 | 6.599 | 0.389 |

### TSP improvement_pct (vs A_pure median=6.560)

| Comparison | improvement_pct | >=5%? |
|------------|----------------|-------|
| B vs A | -0.73% | no |
| C vs A | 0.83% | no |
| D vs A | -3.11% | no |

### TSP Incremental

| Comparison | Δ% |
|------------|-----|
| C vs B | +1.54% |
| D vs C | -3.97% |

---

## Target Assessment

| Criterion | Result | Detail |
|-----------|--------|--------|
| **Primary** (any problem >=5%) | **ACHIEVED** | CVRP C_keyword_outcome = 5.95% |
| Strong (avg across problems >=5%) | NOT MET | avg = 3.39% |

### Primary Success Evidence

- **Problem:** CVRP construct
- **Arm:** C_keyword_outcome (keyword RAG + outcome rerank)
- **improvement_pct:** 5.95%
- **Repeats supporting:** 3/3 (all C runs beat A median)
  - C r1 (12.714) < A median (13.519) ✓
  - C r2 (12.632) < A median (13.519) ✓
  - C r3 (12.886) < A median (13.519) ✓
- **valid_candidates:** 4/4 in all runs (same as A)
- **Failures/collapses:** 0 (same as A)
- **Stability:** C has LOWER std than A (0.130 vs 0.230)

### Why Strong Success Not Met

- TSP best arm (C) only achieves 0.83% improvement
- Average across problems: (5.95 + 0.83) / 2 = 3.39% < 5%
- TSP requires problem-specific investigation (see research_findings.md)

---

## Integrity Checks

- [x] All medians computed from 3 repeats (no cherry-picking)
- [x] A_pure has no anomalous runs (13.13-13.53 range is consistent)
- [x] All arms have valid_candidates=4 in every run
- [x] Zero failures/collapses in any arm
- [x] No parameter changes made to achieve target
- [x] No reranker/multiplier/prompt modifications during experiment
- [x] D arm pop_n=0 noted (population not activating — not masked)

## best_rag_arm

`C_keyword_outcome` (keyword retrieval + outcome-aware rerank)

## best_rag_vs_pure_improvement_pct

- CVRP: **5.95%** (ACHIEVED)
- TSP: 0.83% (not met)
- Average: 3.39% (strong criterion not met)
