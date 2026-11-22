def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = 100
    residual = bins - item
    safe_res = np.maximum(residual, 1e-9)
    class_ratio = item / capacity
    # logistic decay for large residuals
    logistic_weight = 1.0 / (1.0 + np.exp(0.1 * (safe_res - 0.4 * capacity)))
    # harmonic-like penalty: inverse residual for small items, log ratio for large
    harmonic_penalty = np.where(class_ratio > 0.5,
                                1.0 / safe_res,
                                -np.log(safe_res / (item + 1e-9) + 1e-9))
    # utilization–residual product term
    util_residual = (1.0 - np.exp(-item / safe_res)) * safe_res
    scores = logistic_weight * harmonic_penalty + 0.01 * util_residual
    return scores
