def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = np.where(residual == 0, np.inf, -np.log(residual + 1e-10) - (residual < 0.5) * 100)
    return scores
