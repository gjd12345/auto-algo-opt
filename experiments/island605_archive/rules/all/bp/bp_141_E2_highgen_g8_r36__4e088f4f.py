def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    capacity = bins
    fullness = (item / np.maximum(capacity, 1)) ** 2
    log_residual = np.log(1 + 1 / (residual + 1e-10))
    penalty = np.where(residual < item, 0.3 * (1 - residual / (item + 1e-10)), 0.0)
    scores = 0.6 * fullness + 0.4 * log_residual - penalty
    return scores
