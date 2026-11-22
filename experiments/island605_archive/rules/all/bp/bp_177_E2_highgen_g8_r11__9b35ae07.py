def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining = bins - item
    # Penalize small residuals heavily, but boost bins that become 80-100% full
    scores = np.exp(-remaining / 10) + (remaining == 0) * 100 + (0 < remaining) * (remaining <= 0.2 * (bins + item)) * 10
    return scores
