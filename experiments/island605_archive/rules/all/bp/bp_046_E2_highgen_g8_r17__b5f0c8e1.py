def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    relative_gap = residual / (bins + 1e-9)
    entropy = -relative_gap * np.log(relative_gap + 1e-9) - (1 - relative_gap) * np.log(1 - relative_gap + 1e-9)
    utilization = item / bins
    tanh_util = np.tanh(utilization * 3.0)
    log_inverse_gap = np.log(1.0 / (residual + 1e-9) + 1.0)
    scores = tanh_util * log_inverse_gap + 0.5 * entropy
    scores = np.where(np.isfinite(scores), scores, 0.0)
    return scores
