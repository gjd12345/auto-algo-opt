def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    harmonic = -1.0 / (1.0 / (residual ** 2 + 1e-9)).sum() * residual ** 2 if len(bins) > 1 else -residual ** 2
    gap = residual / bins
    penalty = 1.0 / (1.0 + np.exp(-10 * (2 * item - residual)))
    tie_break = np.exp(-np.arange(len(bins), dtype=float) * 1e-6)
    scores = harmonic * penalty + tie_break
    return scores
