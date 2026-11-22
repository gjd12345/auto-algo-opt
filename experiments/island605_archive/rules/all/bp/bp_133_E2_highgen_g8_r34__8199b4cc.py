def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item + 1e-8
    scores = np.exp(item / residual) / ((1.0 + np.arange(len(bins))) ** 1.5)
    return scores
