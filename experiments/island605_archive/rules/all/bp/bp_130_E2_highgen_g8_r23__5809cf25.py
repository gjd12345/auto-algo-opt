def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Avoid division by zero; use a small epsilon
    inv_residual = 1.0 / (residual + 1e-8)
    # Softmax normalization
    exp_inv = np.exp(inv_residual - np.max(inv_residual))
    softmax_scores = exp_inv / np.sum(exp_inv)
    # Logistic penalty for bins with residual below a threshold (e.g., 10% of capacity)
    capacity = bins.max() if bins.size > 0 else 1.0
    threshold = 0.1 * capacity
    logistic_penalty = 1.0 / (1.0 + np.exp(10 * (residual - threshold)))
    # Linear index bonus (1-indexed)
    indices = np.arange(1, len(bins) + 1)
    index_bonus = 0.05 * (1.0 - indices / len(bins))
    return softmax_scores + logistic_penalty + index_bonus
