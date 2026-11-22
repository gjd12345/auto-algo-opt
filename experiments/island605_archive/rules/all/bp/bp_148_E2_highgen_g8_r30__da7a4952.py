def score(item: int, bins: np.ndarray) -> np.ndarray:
    after = bins - item
    residual_ratio = after / (bins.max() + item)
    inverse_squared = 1.0 / (residual_ratio + 1e-6) ** 2
    index_decay = np.exp(-0.5 * np.arange(len(bins)))
    scores = inverse_squared * index_decay
    return scores
