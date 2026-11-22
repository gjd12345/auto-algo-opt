def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = 100
    residual = bins - item
    norm_res = residual / capacity
    # Gaussian penalty centered at 0.2*capacity with sigma=0.06
    penalty = np.exp(-((norm_res - 0.2) ** 2) / (2 * 0.06 ** 2))
    # Quadratic boost near 0 and 0.5*capacity, width=0.08
    boost = (np.maximum(0, 1 - ((norm_res / 0.08) ** 2)) +
             np.maximum(0, 1 - (((norm_res - 0.5) / 0.08) ** 2)))
    scores = 1.0 / (1.0 + residual) + 0.5 * boost - 0.9 * penalty
    return scores
