def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    log_util = np.log(item / (bins + 1e-9) + 1e-9)
    penalty = np.where((residual > 0) & (residual < item * 0.5), (residual ** 2) / (bins + 1), 0)
    return log_util - penalty
