def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    log_score = np.log1p(1.0 / (residual + 1e-6))
    waste_range = (residual > 0) & (residual < item * 0.4)
    penalty = np.where(waste_range, 0.3, 1.0)
    return log_score * penalty
