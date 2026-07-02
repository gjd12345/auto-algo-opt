# Island Model Experiment Report — Final Results

Total runs: 605
Problems: 3
Configuration: gen=8/16, pop=6, operators=e1,e2,m1,m2, OpenCode deepseek-v4-flash
Features: shared pool, best-code seeding, online outcome, adaptive operator, failure sharing

## Results Summary

| Problem | Runs | Baseline | Best | Median | Imp(best) | Imp(median) | >5% rate |
|---------|------|----------|------|--------|-----------|-------------|----------|
| tsp_construct | 206 | 6.5600 | 6.00393 | 6.21286 | +8.5% | +5.3% | 56% |
| cvrp_construct | 207 | 13.5190 | 12.35639 | 12.85885 | +8.6% | +4.9% | 45% |
| bp_online | 192 | 0.0398 | 0.00674 | 0.03687 | +83.1% | +7.3% | 57% |

## Key Findings

### BP Online: Same-Size Reservation Heuristic (+83%)

Best evolved code (obj=0.00674 = 0.67% excess over theoretical lower bound):

```python
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty
```

**Strategy:** Does NOT prefer tight fit. Prefers residual approx item size,
reserving space for future items of similar size. On Weibull distributions
where items cluster around a mode, this achieves near-optimal packing.

### TSP: Full Greedy Chain Projection (+8.5%)

Simulates complete NN chain from each candidate to destination.
Selects candidate minimizing projected total tour length.

### CVRP: Far-First + Depot-Urgency Hybrid (+8.6%)

Two-phase: from depot select farthest customer; during route use
depot-distance urgency (70%) + proximity (30%).

## Distribution Analysis

### tsp_construct (n=206)
- Top 10%: >= 7.2% improvement
- Top 25%: >= 6.2%
- Median: 5.3%
- Bottom 25%: <= 3.8%
- Worse than baseline: 1

### cvrp_construct (n=207)
- Top 10%: >= 6.7% improvement
- Top 25%: >= 5.8%
- Median: 4.9%
- Bottom 25%: <= 4.0%
- Worse than baseline: 1

### bp_online (n=192)
- Top 10%: >= 67.1% improvement
- Top 25%: >= 40.1%
- Median: 7.2%
- Bottom 25%: <= 2.4%
- Worse than baseline: 20

## Experiment Configuration

- API: OpenCode deepseek-v4-flash
- Island Model: 15 gen=8 + 9 gen=16 processes, shared pool
- Evaluator: official EoH (ICML 2024) benchmarks
- Baselines: Round 1 A_pure median (frozen)

## Data Assets

- shared_pool/pool_index.jsonl: 605 run records
- shared_pool/best_codes_*.jsonl: elite code pool per problem
- shared_pool/operator_stats_*.jsonl: operator performance
- evidence/bp_interpretability/: BP best code evidence pack