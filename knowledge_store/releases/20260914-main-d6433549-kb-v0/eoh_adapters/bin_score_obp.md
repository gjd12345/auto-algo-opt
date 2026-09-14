# EoH adapter: Online bin packing — score / priority

Registered problem_id: `obp_online`.

Official examples use score+argmax. Frozen/session uses priority+first maximum. Template return bins is Worst Fit. -bins is Best-Fit-like.

Plan JSON cannot contain a `code` field. Put the mechanism in `operations[].mechanism`. If a later seed is required, use `explicit_seeds` and label it as an adapter, not the original paper algorithm.

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
