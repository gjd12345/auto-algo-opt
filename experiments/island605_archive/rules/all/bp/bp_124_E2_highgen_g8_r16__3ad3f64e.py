def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = 1.0 / (residual ** 2 + 1e-10) + np.exp(-0.01 * np.arange(len(bins)))
    return scores
