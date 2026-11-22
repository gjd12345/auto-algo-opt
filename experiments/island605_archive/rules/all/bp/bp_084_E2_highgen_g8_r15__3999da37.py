def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max() + item
    target_remaining = 0.3 * capacity  # prefer bins left with 30% free space
    residual_after = bins - item
    closeness = 1.0 / (np.abs(residual_after - target_remaining) + 1e-10)
    tightness_penalty = 1.0 / (residual_after + 1e-10)
    position_bonus = np.exp(-0.1 * np.arange(len(bins)))  # exponential decay
    scores = closeness * tightness_penalty * position_bonus
    return scores
