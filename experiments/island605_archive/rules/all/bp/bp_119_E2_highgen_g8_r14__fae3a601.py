def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target = 0.3 * bins.max()
    gap_penalty = (residual - target) ** 2
    index_weights = np.arange(len(bins), 0, -1) ** 1.5
    scores = -gap_penalty * index_weights
    return scores
