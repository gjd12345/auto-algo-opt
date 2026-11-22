def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    penalty = np.log(1 + residual / bins.max())
    scores = np.exp(-residual) * (1 - penalty) + (1 - np.arange(len(bins)) * 1e-9)
    return scores
