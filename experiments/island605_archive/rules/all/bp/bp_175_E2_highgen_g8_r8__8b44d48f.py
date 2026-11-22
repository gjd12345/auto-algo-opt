def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fullness_ratio = item / bins
    # Prefer high fullness but penalize residuals that are very small (likely wasted)
    # and also penalize if the bin is too large relative to item (poor fit for future).
    # Score = fullness_ratio - (residual / bins) * 0.5  -> simplifies to (item - 0.5*residual)/bins
    scores = (item - 0.5 * residual) / bins
    # Tie-break: add small preference for earlier bins (lower index)
    scores -= np.arange(len(scores)) * 1e-12
    return scores
