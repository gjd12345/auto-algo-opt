def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    exact_fit = residual == 0
    epsilon = 1e-12
    scores = np.where(exact_fit, np.inf, 1.0 / (residual + epsilon) ** 2)
    scores += np.arange(len(bins)) * 1e-10
    return scores
