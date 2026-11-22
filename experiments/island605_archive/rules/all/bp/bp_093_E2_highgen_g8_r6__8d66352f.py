def score(item: int, bins: np.ndarray) -> np.ndarray:
    ratio = item / bins
    residual = bins - item
    util = residual / np.maximum(bins, 1)
    harmonic_penalty = np.where(ratio > 0.7, 6, np.where(ratio > 0.4, 2, 0))
    score_val = (1 - util) * 60 + (residual ** 0.5) * 1.5 - harmonic_penalty + (util ** 2) * 30
    return score_val
