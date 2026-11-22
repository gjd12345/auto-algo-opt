def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Quadratic penalty: smallest at residual = capacity/2, growing for very small or large residuals
    penalty = (residual - (bins.max() / 2.0)) ** 2
    # Bonus for bins that become full (residual == 0) to encourage complete usage
    full_bonus = np.where(residual == 0, 1e6, 0.0)
    return -penalty + full_bonus
