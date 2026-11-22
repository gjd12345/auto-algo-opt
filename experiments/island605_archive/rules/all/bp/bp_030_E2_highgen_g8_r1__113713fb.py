def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Exponential reward for high utilization
    util_reward = np.exp(10 * (bins - residual) / bins.max() - 1)
    # Cubic penalty for residual waste less than item
    gap_penalty = np.where(residual > 0, (np.maximum(0, item - residual) / item) ** 3, 0)
    # Fixed bonus for residual == 1
    one_bonus = 0.8 * (residual == 1).astype(float)
    score_val = util_reward - gap_penalty + one_bonus
    return score_val
