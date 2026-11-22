def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    ratio = residual / item
    # Convex penalty for large residuals (wasteful bins)
    waste_penalty = np.maximum(0, ratio - 2) ** 2 * 3
    # Reward for exact multiples of item (tight packing)
    multiple_bonus = np.where(np.abs(ratio - np.round(ratio)) < 0.1, 2.0, 0.0)
    # Penalize residual < 0 (should not occur) but ensure negative scores never win
    safety_penalty = np.where(residual < 0, -1e9, 0)
    scores = -waste_penalty + multiple_bonus + safety_penalty
    return scores
