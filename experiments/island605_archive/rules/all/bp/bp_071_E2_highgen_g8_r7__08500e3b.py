def score(item: int, bins: np.ndarray) -> np.ndarray:
    utilization = item / bins
    residual = bins - item
    tiny = 0.2 * (bins.max() if bins.max() > 0 else 1.0)
    penalty = np.exp(-residual / tiny) * (residual < tiny)
    scores = utilization - 0.5 * penalty
    return scores
