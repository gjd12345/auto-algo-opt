def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins[0] + item if len(bins) > 0 else item
    residual = bins - item
    harmonic_score = 1.0 / (1.0 + residual) + 1.0 / (1.0 + (capacity - residual))
    scores = harmonic_score / (1.0 + 0.1 * abs(residual - item))
    return scores
