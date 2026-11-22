def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_ratio = item / (bins + item)
    # Exponential penalty for residuals that are non-zero but small
    penalty = np.exp(-residual / (bins + 1e-9))
    # Bonus for residuals that are zero or exactly divisible by item
    divisor_bonus = np.where((residual == 0) | (residual % item == 0), 10.0, 0.0)
    scores = fill_ratio * (1.0 + penalty) + divisor_bonus
    return scores
