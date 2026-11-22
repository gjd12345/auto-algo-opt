def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    capacity = bins.max() + item
    reward = 1.0 / (1.0 + residual ** 0.5)
    penalty = 0.2 * np.abs(np.cos(residual * np.pi / 5.0))
    linear_scale = item / capacity
    scores = reward * (1.0 - penalty) * linear_scale
    scores = np.where(np.isfinite(scores), scores, -residual)
    return scores
