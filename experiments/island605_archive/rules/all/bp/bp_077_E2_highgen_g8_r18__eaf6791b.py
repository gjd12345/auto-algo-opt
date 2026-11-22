def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target_multiple = np.round(residual / (item + 1)) * (item + 1)
    deviation_penalty = np.square(residual - target_multiple)
    fullness_bonus = np.exp(-residual / (item * 0.3))
    linear_bonus = residual / (item * 3)
    scores = -deviation_penalty * 0.05 + fullness_bonus * 2.0 + linear_bonus
    return scores
