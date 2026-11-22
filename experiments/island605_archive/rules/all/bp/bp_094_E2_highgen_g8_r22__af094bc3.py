def score(item: int, bins: np.ndarray) -> np.ndarray:
    resid = bins - item
    # Inverse cubic penalty for residual waste (larger waste = lower score)
    waste_penalty = 1.0 / (resid ** 3 + 1)
    # Collision bonus: reward bins whose resid is near any integer multiple of capacity
    capacity = bins[0] + item  # all bins share same capacity
    capacity_multiple = (resid % capacity) / capacity
    cluster_bonus = np.exp(-20 * capacity_multiple)  # peaks at resid multiple of capacity
    # Small linear index tiebreaker
    tiebreaker = np.linspace(0, 1, len(bins))[::-1] * 0.001
    scores = waste_penalty + cluster_bonus + tiebreaker
    return scores
