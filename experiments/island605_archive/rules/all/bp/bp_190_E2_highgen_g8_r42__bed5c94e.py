def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = residual / (bins + 1e-9)  # harmonic component: larger residual -> lower score
    scores = 1 / (scores + 1e-9)  # invert so smaller residual -> higher score
    scores[residual == 0] = 1e9  # strong bonus for exact fit
    return scores
