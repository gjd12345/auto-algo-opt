def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fullness = 1 - residual / bins.max()
    sigmoid_weight = 1 / (1 + np.exp(-10 * (fullness - 0.5)))
    decay = np.exp(-2 * residual)
    score = sigmoid_weight * decay
    penalty = np.where(residual < 0.1 * bins.max(), (residual / bins.max()) ** 2, 0)
    return score - penalty
