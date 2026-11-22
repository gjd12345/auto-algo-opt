def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty