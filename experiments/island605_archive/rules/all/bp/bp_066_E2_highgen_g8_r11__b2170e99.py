def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / (bins + 1e-8)
    penalty = np.where((residual > 0) & (residual <= 0.3 * bins.max()), np.log1p(residual), 0)
    fullness_bonus = 0.05 * (1 - np.exp(-bins / (bins.max() + 1e-8)))
    scores = np.exp(utilization) - penalty + fullness_bonus
    return scores
