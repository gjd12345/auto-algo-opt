def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fit_ratio = item / residual  # higher when item nearly fills bin
    index_penalty = 1.0 / (np.arange(len(bins)) + 1)  # decreasing harmonic penalty for later bins
    scores = fit_ratio * index_penalty
    return scores
