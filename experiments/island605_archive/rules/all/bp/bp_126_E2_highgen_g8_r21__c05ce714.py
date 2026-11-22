def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Avoid division by zero by adding a small epsilon
    epsilon = 1e-6
    scores = 1.0 / (residual + epsilon) ** 2 - np.arange(len(bins)) * 0.01
    return scores
