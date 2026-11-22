def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    power = np.where(residual < item * 0.5, 3.0, np.where(residual < item * 2.0, 1.2, 2.5))
    inv_residual = 1.0 / (residual ** power + 1e-9)
    mid_bonus = np.exp(-4.0 * ((residual / (item + 1e-9)) - 1.0) ** 2)
    small_penalty = np.exp(-10.0 * (residual / (item + 1e-9)))
    scores = inv_residual * (1.0 + 0.5 * mid_bonus) * (1.0 - 0.3 * small_penalty)
    return scores
