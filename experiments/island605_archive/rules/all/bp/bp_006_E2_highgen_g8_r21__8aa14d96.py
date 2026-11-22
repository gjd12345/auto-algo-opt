def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target = (bins.max() + item) / 3  # dynamic target based on current capacities
    # score: exponential decay based on deviation from target, with penalty for very small residuals
    scores = np.exp(-0.1 * np.abs(residual - target))
    scores = np.where(residual <= 2, scores * 0.3, scores)  # penalize tight residuals
    scores = np.where(residual == 0, 1e6, scores)  # exact fit gets high bonus
    return scores
