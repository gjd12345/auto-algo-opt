def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    median_res = np.median(residual)
    fit_ratio = item / (bins + 1e-9)
    fullness_penalty = -((residual - median_res) / (bins.max() + 1e-9)) ** 2
    index_bonus = 0.001 * np.arange(len(bins))[::-1]
    scores = fit_ratio + fullness_penalty + index_bonus
    return scores
