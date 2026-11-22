def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    n = len(bins)
    # logarithmic decay: higher score for later bins (index from end)
    pos_weight = np.log(1 + np.arange(n) + 1) / np.log(n + 2)
    # closeness to item size: high when residual is small
    closeness = 1 / (1 + residual)
    return -np.cbrt(residual + 1e-9) * closeness * pos_weight
