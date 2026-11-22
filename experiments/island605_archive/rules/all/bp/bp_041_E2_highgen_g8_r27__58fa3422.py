def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / np.maximum(bins, 1e-8)
    sigmoid_util = 1.0 / (1.0 + np.exp(-6.0 * (utilization - 0.45)))
    prime_penalty = np.where(
        (residual > 0) & (residual < item * 0.5),
        np.log(1.0 + residual) / (1.0 + np.abs(residual % 3) * 0.3 + np.abs(residual % 5) * 0.2),
        0.0
    )
    even_boost = np.cos(0.5 * np.pi * (bins % 2)) * 0.03
    scores = sigmoid_util - 0.35 * prime_penalty + even_boost
    return scores
