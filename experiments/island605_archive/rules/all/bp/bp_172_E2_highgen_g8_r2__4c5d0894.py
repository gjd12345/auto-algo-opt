def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_bin = np.max(bins)
    # Primary: prefer smallest residual (best-fit); secondary: prefer bins with smaller original capacity (fuller bins)
    # To combine: negate residual for max preference, add tiny bonus for smaller original capacity
    # Use max_bin to normalize secondary term to avoid dominating primary
    return -residual + (max_bin - bins) * 1e-6
