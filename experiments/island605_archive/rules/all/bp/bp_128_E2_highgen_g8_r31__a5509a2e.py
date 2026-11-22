def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    ratio = item / (residual + 1e-8)
    scores = np.exp(-residual / 10.0) * np.log(ratio + 1e-8)
    return scores
