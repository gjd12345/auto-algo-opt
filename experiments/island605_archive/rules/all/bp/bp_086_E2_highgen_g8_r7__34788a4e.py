def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Smoothly penalize residuals near 0 or near multiples of item (wastes)
    distance_penalty = np.sin(np.pi * residual / (item + 1e-9)) ** 2
    # Harmonic-like blend: high utilization and avoid "awkward" gaps
    utilization = 1.0 - residual / (bins + 1e-9)
    scores = 2 * utilization * (1 - distance_penalty) / (utilization + (1 - distance_penalty) + 1e-9)
    return np.nan_to_num(scores, nan=0.0)
