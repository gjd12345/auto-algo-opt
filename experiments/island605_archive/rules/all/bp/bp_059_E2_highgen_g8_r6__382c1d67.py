def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization_sigmoid = 1 / (1 + np.exp(-5 * (item / bins - 0.5)))
    residual_penalty = np.log(1 + residual / bins) * np.where(residual < 0.3 * bins, 2.0, 0.0)
    capacity_bonus = bins / (bins.max() + 1e-9)
    scores = utilization_sigmoid - residual_penalty + 0.1 * capacity_bonus
    return scores
