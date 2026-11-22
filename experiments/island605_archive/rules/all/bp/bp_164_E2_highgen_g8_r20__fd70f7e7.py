def score(item: int, bins: np.ndarray) -> np.ndarray:
    ideal = (bins - item) / 2.0
    distance = (bins - item - ideal) ** 2
    priority = 1.0 + np.sin(np.arange(len(bins)) * 0.5)
    return 1.0 / (distance + 1e-8) * priority
