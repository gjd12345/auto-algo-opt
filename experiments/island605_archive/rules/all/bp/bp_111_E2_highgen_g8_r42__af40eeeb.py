def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    original_capacity = bins + item
    residual_after = bins - item
    tightness = np.exp(-residual_after) * original_capacity
    index_bonus = 0.5 / (1 + np.arange(len(bins)))
    scores = tightness + index_bonus
    return scores
