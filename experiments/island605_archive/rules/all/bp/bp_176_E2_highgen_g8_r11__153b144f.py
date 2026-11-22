def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Score: higher for smaller residual, with a small index bias for determinism
    scores = -residual - np.arange(len(bins)) * 1e-9
    return scores
