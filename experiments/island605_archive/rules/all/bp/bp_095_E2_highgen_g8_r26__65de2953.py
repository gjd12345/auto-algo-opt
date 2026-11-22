def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Score based on how well residual aligns with item size: prefer small residuals that are multiples of item
    scores = np.where(residual == 0, 1e9, -np.abs(residual % item) - residual / item)
    return scores
