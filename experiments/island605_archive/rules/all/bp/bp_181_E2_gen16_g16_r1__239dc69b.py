def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    log_penalty = np.log(residual + 1e-6)
    scores = utilization + 1.0 / (residual + 0.1) - 0.1 * log_penalty
    return scores
