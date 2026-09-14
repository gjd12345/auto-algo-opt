# Best Fit / Almost Best Fit

Literature method card from an OpenAlex abstract plus grok-4.5 screen. This is not a main-tree implementation.

## 定义或方法步骤

- Apply Best Fit / Almost Best Fit as introduced in Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms (1974).
- Prefer tight residual.
- Abstract-supported identity only; do not copy publisher PDF.

Why selected: DOI-seeded canonical paper for obp_bestfit_family.

## 适用条件、假设与限制

Subproblem: Best-Fit online family — Prefer tight residual.

DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

## 来源及支持的具体结论

Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms (1974). DOI 10.1137/0203025. read_depth=abstract. Do not copy publisher PDF into the release.

## 代码和评测关联

No local code hash. Evaluator remains the only scorekeeper. If used as an EoH seed later, mark it as an adapter, not the original algorithm.

## 未确认项与冲突证据

Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.

## EoH 适配

- target_problem_id: obp_online
- adapter_kind: bin_score
- mappable: possible
- not_the_original: DOI-directed fill. Adapter is not the original algorithm unless the abstract already matches the entrypoint.

```python
def score(item: float, bins: np.ndarray) -> np.ndarray:
    """Official-example OBP adapter. bins are feasible residuals only.

    Evaluator does argmax. Template `return bins` is Worst Fit. `-bins` is
    Best-Fit-like. First Fit is not a score over residuals; it is scan order.
    """
    # mechanism: one numeric score per feasible residual
    return -bins

def priority(item: float, bins: np.ndarray) -> np.ndarray:
    """Frozen/session OBP adapter. Same semantics as score; first maximum wins.

    Empty `bins` means the evaluator opens a new bin. Do not open bins here.
    """
    # mechanism: one numeric priority per feasible residual
    return -bins
```

Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。
