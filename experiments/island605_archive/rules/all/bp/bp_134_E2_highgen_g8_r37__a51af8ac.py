def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual_after = bins - item
    scores = np.exp(-residual_after) - 1e-6 * np.arange(len(bins))
    return scores
