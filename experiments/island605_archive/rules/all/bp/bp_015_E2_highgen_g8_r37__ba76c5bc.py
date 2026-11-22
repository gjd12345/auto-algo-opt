def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fullness = (bins - residual) / np.maximum(bins, 1)
    half_deviation = np.abs(fullness - 0.5)
    log_penalty = -np.log(1 + half_deviation * 10)
    extreme_bonus = np.exp(10 * (fullness - 0.9)) * (fullness > 0.9)
    scores = log_penalty + extreme_bonus
    # tie-break by original index (stable order)
    scores = scores + np.arange(len(bins)) * 1e-12
    return scores
