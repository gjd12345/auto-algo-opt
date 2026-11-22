def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining = bins - item
    # Score based on logistic of residual, preferring small residuals, plus first-fit index bonus
    scores = 1.0 / (1.0 + np.exp(remaining * 0.5))  # higher score for smaller residual
    indices = np.arange(len(bins))
    return scores * 1e6 + 1e4 / (indices + 1)  # scale logistic, add strong index bonus
