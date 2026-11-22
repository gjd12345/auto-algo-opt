def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = -np.cbrt(residual) - 0.1 * np.arange(len(bins))
    return scores
