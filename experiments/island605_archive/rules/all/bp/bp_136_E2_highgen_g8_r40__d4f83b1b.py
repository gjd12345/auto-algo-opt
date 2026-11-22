def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    rem = bins - item
    util = item / bins
    fullness_scores = 1.0 / (rem * rem + 1e-9)
    modulation = 1.0 / (1.0 + np.exp(-10.0 * (util - 0.8)))
    scores = fullness_scores * modulation
    scores -= np.arange(len(bins)) * 0.01
    return scores
