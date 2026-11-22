def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = 1.0 / (residual ** 2 + 0.01) - np.exp(np.arange(len(bins)) * 0.01)
    return scores
