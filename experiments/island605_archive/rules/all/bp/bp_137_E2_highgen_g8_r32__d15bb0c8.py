def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Simulate item count per bin by reverse index proxy; penalize high residual * low index
    proxy_item_count = np.arange(len(bins), 0, -1)  # later bins have higher proxy count
    scores = -residual * proxy_item_count
    return scores
