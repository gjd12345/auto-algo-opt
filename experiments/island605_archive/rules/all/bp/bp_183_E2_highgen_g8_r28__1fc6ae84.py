def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max()
    residual = bins - item
    # Linear residual penalty (prefer smaller residual)
    linear_penalty = residual
    # Quadratic utilization bonus (prefer higher fill)
    utilization_bonus = (1 - residual / capacity) ** 2 * 500.0
    # Score: lower residual is good, high utilization is good
    scores = -linear_penalty + utilization_bonus
    return scores
