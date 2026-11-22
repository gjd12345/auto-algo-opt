def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining = bins - item
    exact_fit = (remaining == 0).astype(float) * 1e9
    penalty = np.where(remaining > 0, (remaining - 0.5 * bins.max())**2, 0)
    utilization_bonus = bins / bins.max()
    scores = exact_fit - penalty + utilization_bonus
    return scores
