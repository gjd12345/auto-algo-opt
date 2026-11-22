def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    zero_bonus = np.where(residual == 0, 1e6, 0)
    target_residual = bins * 0.5
    closeness = -np.abs(residual - target_residual)
    penalty = np.where((residual > 0) & (residual < item * 0.5), -1e3, 0)
    return closeness + zero_bonus + penalty
