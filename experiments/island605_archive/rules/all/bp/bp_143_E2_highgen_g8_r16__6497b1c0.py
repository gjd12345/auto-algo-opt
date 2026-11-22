def score(item: int, bins: np.ndarray) -> np.ndarray:
    residuals = bins - item
    # Use squared reciprocal to heavily penalize larger residuals
    base_scores = 1.0 / (residuals ** 2 + 1e-10)
    # Quadratic penalty for later indices: higher index gets lower score
    index_penalty = 1.0 / (np.arange(len(bins)) + 1) ** 2
    return base_scores * index_penalty
