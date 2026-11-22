def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    # Fractional part of (residual / item), then invert so smaller fraction gets higher score
    frac = (residual / item) - np.floor(residual / item)
    scores = np.exp(-10 * frac)
    return scores
