def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    inv_sq = 1.0 / (residual ** 2 + 1e-10)
    weights = 1.0 / (1.0 + np.arange(len(bins)))
    scores = inv_sq * weights
    return scores
