def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_ratio = item / bins
    return -np.log(residual + 1e-8) - fill_ratio
