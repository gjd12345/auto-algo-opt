def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_ratio = item / bins
    residual_score = np.exp(-0.8 * residual)
    index_decay = np.exp(-0.05 * np.arange(len(bins)))
    fill_penalty = np.sqrt(1 - fill_ratio)
    return residual_score + 0.5 * index_decay - 0.3 * fill_penalty
