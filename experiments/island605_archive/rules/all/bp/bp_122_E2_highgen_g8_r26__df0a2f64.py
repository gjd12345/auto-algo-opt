def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Rational penalty for gaps matching item // k for k=2,3,4
    penalty = np.where(
        (residual == item // 2) | (residual == item // 3) | (residual == item // 4),
        0.5, 0.0
    )
    # Linear utilization gain (fraction of bin used)
    util = 1.0 - (residual / (bins + 1e-6))
    # Sigmoid decay for very small gaps (residual < item/5)
    decay = 1.0 / (1.0 + np.exp(10.0 * (residual / (item + 1e-6) - 0.2)))
    scores = 1.2 * util + 0.3 * decay - penalty
    return scores
