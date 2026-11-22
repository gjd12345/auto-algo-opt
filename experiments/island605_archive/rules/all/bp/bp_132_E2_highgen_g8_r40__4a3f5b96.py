def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # cubic compression for tight packing
    tightness = 1.0 / (1.0 + residual) ** 3
    # step penalty at mod 13 to break ties
    penalty = np.where(residual % 13 == 0, 0.05, 0.0)
    # index-based tiebreaker with negligible weight
    scores = tightness - 1e-12 * np.arange(len(bins)) - penalty
    return scores
