def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_bin = bins.max() + 1
    util_gain = np.tanh(residual / max_bin)
    cubic_penalty = - (residual ** 3) / (max_bin ** 3)
    residual_clamped = np.where(residual > 0, residual, 1)
    log_bonus = np.log(1 + (item % residual_clamped == 0).astype(float) / (residual_clamped + 1))
    return util_gain + cubic_penalty + log_bonus
