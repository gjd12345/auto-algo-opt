def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max()
    repulsion_points = np.array([capacity / 2, capacity / 3, capacity / 5])
    current_load = capacity - bins
    post_load = current_load + item
    distances = np.min(np.abs(post_load[:, None] - repulsion_points), axis=1)
    primary = distances
    secondary = -np.exp(np.arange(len(bins)) * 0.01)
    return primary + secondary
