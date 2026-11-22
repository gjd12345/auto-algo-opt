def score(item: int, bins: np.ndarray) -> np.ndarray:
    # Reward high residual capacity after placing item, scaled negatively to keep preference for fuller bins
    residual = bins - item
    # Combine: prefer smaller residual (fuller bins) but add a quadratic penalty for very small residual to avoid waste
    scores = -residual + 0.01 * (residual ** 2)
    # Add reverse index tie-breaker (higher index gets slight advantage) to spread selection
    scores -= np.arange(len(bins)) * 1e-8
    return scores
