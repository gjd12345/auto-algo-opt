def score(item: int, bins: np.ndarray) -> np.ndarray:
    half = (bins.max() + 1) // 2  # approximate capacity / 2
    if item > half:
        # Large item: prefer worst-fit (largest residual) to avoid opening new bins
        return bins
    else:
        # Small/medium item: prefer best-fit (smallest residual >= item)
        # Invert so that smaller residual gets higher score
        max_cap = bins.max()
        return max_cap - bins
