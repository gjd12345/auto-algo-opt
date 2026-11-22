def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_res = np.max(bins)
    harmonic = 1.0 / ((residual + 1.0) ** 2)
    diversity = np.abs(bins / max_res - 0.5) if max_res > 0 else np.zeros_like(bins)
    scores = harmonic + 0.6 * (1.0 - diversity)
    return scores
