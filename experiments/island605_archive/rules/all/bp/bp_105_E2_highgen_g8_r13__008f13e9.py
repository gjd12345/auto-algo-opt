def score(item: int, bins: np.ndarray) -> np.ndarray:
    # Primary: penalize wasted residual capacity quadratically (smaller residual = higher score)
    residual = bins - item
    max_cap = bins.max() + 1
    primary = (1 - (residual / max_cap)) ** 2
    # Bonus: bins where residual is a multiple of item size get a boost
    boost = np.where(residual % item == 0, 0.5, 0.0)
    # Tie-breaker: prefer lower index
    tie = -np.arange(len(bins), dtype=float) * 1e-9
    return primary + boost + tie
