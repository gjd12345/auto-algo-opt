def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    capacity = bins.max()
    residual = bins - item
    # Primary: exponential decay of relative residual, inverted so tight fit scores higher
    primary = np.exp(-residual / capacity * 8)
    # Secondary boost for bins leaving residual exactly equal to item (potential perfect fit later)
    secondary = np.where(residual == item, 0.5, 0.0)
    return primary + secondary
