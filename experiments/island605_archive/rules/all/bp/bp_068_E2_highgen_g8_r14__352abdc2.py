def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    nearest_multiple = np.round(residual / item) * item
    scores = -np.abs(residual - nearest_multiple) * 1000 + residual
    return scores
