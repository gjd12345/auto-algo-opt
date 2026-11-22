def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_score = 1.0 / (residual * residual + 1e-12)
    index_bonus = 1.0 - 0.05 * np.arange(len(bins))
    scores = fill_score + index_bonus
    return scores
