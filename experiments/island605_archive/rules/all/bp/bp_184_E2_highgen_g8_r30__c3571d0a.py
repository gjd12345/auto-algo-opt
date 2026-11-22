def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_res = np.max(residual)
    penalty = residual ** 2
    bonus = np.where(residual > max_res * 0.8, 0.1 * residual, 0.0)
    return -penalty + bonus
