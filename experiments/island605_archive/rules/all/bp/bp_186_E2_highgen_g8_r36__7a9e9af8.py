def score(item: int, bins: np.ndarray) -> np.ndarray:
    # Novel scoring: prefer bin with highest effective density after placement,
    # measured as (capacity - residual) / capacity, but biased toward smaller residuals.
    # Score = (capacity - (residual - item)) / capacity + 1 / (residual - item + 1)
    capacity = np.max(bins + item)  # assume all bins share same original capacity
    residual_after = bins - item
    density = (capacity - residual_after) / capacity
    waste_penalty = 1.0 / (residual_after + 1)
    return density + waste_penalty
