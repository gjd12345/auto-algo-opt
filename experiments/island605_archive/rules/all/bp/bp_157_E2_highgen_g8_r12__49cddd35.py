def score(item: int, bins: np.ndarray) -> np.ndarray:
    scores = 1.0 / ((bins - item) ** 3 + 1e-9)
    residual = bins - item
    penalty = (residual < 0.2 * bins.max()).astype(float) * 0.5
    scores *= (1 - penalty)
    return scores
