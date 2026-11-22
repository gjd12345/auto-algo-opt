def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    return - (residual ** 2) + (residual * 0.01)
