def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    perfect_bonus = (residual == 0).astype(float) * 1e6
    harmonic_decay = 1.0 / (np.arange(len(bins)) + 1)
    scores = (residual ** 2) * harmonic_decay + perfect_bonus
    return scores
