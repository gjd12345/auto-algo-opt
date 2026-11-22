def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util_score = 1.0 / (1.0 + np.exp(0.5 * (residual - 1.0)))
    index_decay = -np.log(np.arange(1, len(bins) + 1) + 1.0) * 0.1
    return util_score + index_decay
