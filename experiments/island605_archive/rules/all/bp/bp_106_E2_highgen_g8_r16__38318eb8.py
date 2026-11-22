def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    safe_residual = np.where(residual == 0, 1e-9, residual)
    base_score = np.exp(-(safe_residual ** 3))
    power_of_two = (residual > 0) & ((residual & (residual - 1)) == 0) & ((residual % 2) == 0)
    bonus = np.where(power_of_two, 1000.0, 1.0)
    return base_score * bonus
