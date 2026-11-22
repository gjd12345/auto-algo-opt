def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target = 0.3 * (bins + item)  # sweet spot based on original capacity
    diff = np.abs(residual - target)
    scores = np.exp(-diff / (bins + 1e-9))  # Gaussian-like decay; high when residual near target
    # Boost bins that become exactly full
    scores[residual == 0] = np.inf
    return scores
