def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    gap_penalty = np.where(residual > 0, 1.0 / (1.0 + np.log(1.0 + residual)), 0.0)
    poly_penalty = np.where(residual > 0, residual**0.5, 0.0)
    scores = utilization + 0.1 * gap_penalty - 0.05 * poly_penalty
    return scores
