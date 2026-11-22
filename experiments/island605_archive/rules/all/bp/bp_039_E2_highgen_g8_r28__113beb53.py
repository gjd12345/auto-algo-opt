def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    base_score = np.exp(1.0 / (residual + 1e-10))
    penalty = 0.2 * (residual < 0.3 * bins.mean()).astype(float)
    scores = base_score - penalty
    return scores
