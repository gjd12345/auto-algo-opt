def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    common_sizes = np.array([10, 20, 50, 100])
    residual_penalty = np.sum(np.exp(-0.5 * ((residual[:, None] - common_sizes) / 5) ** 2), axis=1)
    capacity_bonus = np.log(1 + bins / 100)
    scores = 0.5 * utilization - 0.4 * residual_penalty + 0.1 * capacity_bonus
    return scores
