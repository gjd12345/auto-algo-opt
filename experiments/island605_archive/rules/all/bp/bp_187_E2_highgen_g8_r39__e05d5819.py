def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual_after = bins - item
    mean_residual = np.mean(residual_after)
    variance_penalty = np.abs(residual_after - mean_residual)
    scores = -residual_after - 0.1 * variance_penalty - np.arange(len(bins)) * 1e-9
    return scores
