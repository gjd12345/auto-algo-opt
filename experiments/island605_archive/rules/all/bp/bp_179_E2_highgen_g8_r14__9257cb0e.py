def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Reward: utilization after placing item, normalized
    util = (item / bins).clip(0, 1)
    # Penalty: polynomial on residual gaps that are likely wasted (< item or < 3)
    small_gap_penalty = np.where(residual > 0, (residual / (residual + 1)) ** 2, 0)
    # Boost for tight fits: residual exactly 0 is best
    tight_bonus = np.where(residual == 0, 1.0, 0.0)
    scores = util + tight_bonus - 0.3 * small_gap_penalty
    return scores
