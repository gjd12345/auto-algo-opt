def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    reward = 1 / (1 + (residual + 1e-10) ** 2.0)
    cos_penalty = 0.3 * np.abs(np.cos(4 * np.pi * residual / (item + 1e-10)))
    full_penalty = 0.4 * (1 - residual / (item + bins.max() + 1e-10))
    scores = reward + cos_penalty - full_penalty
    scores = np.clip(scores, -1e9, 1e9)
    scores[~np.isfinite(scores)] = 0.0
    return scores.astype(np.float64)
