def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fullness = 1 - residual / bins
    target = 0.8
    balance = 1 / (1 + np.exp(10 * (fullness - target)))
    scores = np.exp(-residual / (fullness ** 2 + 1e-8)) * (1 - balance)
    scores -= np.arange(len(bins)) * 1e-9
    return scores
