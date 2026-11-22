def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    penalty = np.where((residual > 0) & (residual <= item * 0.4), residual**3, 0)
    smooth_tiebreak = 0.5 * (1 + np.cos(2 * np.pi * (utilization - 0.5)))
    scores = np.log(utilization + 1e-9) - penalty / (bins + 1e-9) + smooth_tiebreak * 0.05
    return scores
