def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target_half = bins / 2.0
    penalty = np.where(residual < target_half, (target_half - residual) ** 2, 0)
    reward = np.where(residual == 0, 1e6, 0)
    return -penalty + reward
