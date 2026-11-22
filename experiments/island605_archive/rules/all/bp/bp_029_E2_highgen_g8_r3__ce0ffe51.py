def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    penalty = np.where(residual < item / 2, residual ** 2, 0)
    bonus = np.where(residual >= item / 2, residual * (item / bins), 0)
    return -residual - penalty + bonus
