def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    capacity_ratio = item / bins
    threshold_bonus = np.where((bins >= 2 * item) & (bins < 3 * item), 1.0, 0.0)
    waste_penalty = np.log1p(bins)  # logarithmic penalty for larger bins
    tie_breaker = np.arange(len(bins), 0, -1) * 1e-12
    return capacity_ratio + threshold_bonus - waste_penalty + tie_breaker
