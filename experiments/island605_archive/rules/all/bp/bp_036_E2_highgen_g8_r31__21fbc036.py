def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util = np.exp(item / bins) - 1
    gap_penalty = np.where((residual > 0) & (residual < item * 0.5), residual ** 3, 0.0)
    near_fit_bonus = np.where((residual > 0) & (residual <= 2), np.log(residual + 1), 0.0)
    scores = 0.8 * util - 0.005 * gap_penalty + 0.1 * near_fit_bonus
    return scores
