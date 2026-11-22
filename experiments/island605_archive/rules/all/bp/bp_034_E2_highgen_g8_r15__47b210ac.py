def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    normalized_residual = residual / bins
    log_util = np.log(normalized_residual + 1e-12)
    sigmoid_penalty = 1 / (1 + np.exp(-10 * (normalized_residual - 0.2)))
    penalty = np.where((residual > 0) & (residual < item * 0.5), sigmoid_penalty * residual, 0)
    scores = -log_util - penalty
    return scores
