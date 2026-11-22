def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    mod_ratio = residual / item
    score = -np.abs(mod_ratio - np.round(mod_ratio))
    # Tie-break by index: add tiny decreasing sequence
    score -= np.arange(len(bins)) * 1e-10
    return score
