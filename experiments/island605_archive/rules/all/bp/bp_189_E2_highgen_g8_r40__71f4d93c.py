def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    penalty = (residual / bins) ** 3
    scores = utilization - penalty
    return scores
