def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    capacity = bins.max() + item  # estimate total capacity
    target_remaining = 0.3 * capacity
    closeness = 1.0 / (1.0 + np.abs(residual - target_remaining))
    full_bonus = (residual == 0).astype(float) * 10.0
    return closeness + full_bonus
