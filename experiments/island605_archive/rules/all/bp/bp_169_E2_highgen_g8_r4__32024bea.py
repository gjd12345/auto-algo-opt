def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    tightness = 1.0 / (residual + 1e-9)
    penalty = 1.0 - 0.5 * (residual == item).astype(float)
    scores = tightness * penalty
    return scores
