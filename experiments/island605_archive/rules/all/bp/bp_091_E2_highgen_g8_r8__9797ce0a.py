def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    primary = 1.0 / (residual + 1e-9)
    mod_factor = np.where(residual % 4 == 0, 0.2, np.where(residual % 2 == 0, 0.1, -0.1))
    scores = primary + mod_factor
    return scores
