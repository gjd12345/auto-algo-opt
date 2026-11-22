def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    sigma = max(item, 1)
    scores = np.exp(-((residual - item) ** 2) / (2 * sigma ** 2))  # Gaussian peak when residual ≈ item
    scores += 1.0 / (residual + 1e-9)  # harmonic decay for larger residuals
    scores = np.where(residual == item, scores + 1e5, scores)  # big bonus for exact match with item size
    return scores
