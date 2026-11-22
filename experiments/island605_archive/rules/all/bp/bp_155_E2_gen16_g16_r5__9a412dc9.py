def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    max_cap = bins.max() if bins.max() > 0 else 1
    util_gain = np.exp((bins - item) / max_cap) - 1.0
    residual = bins - item
    gap_penalty = (item / (residual + 1e-8)) ** 2
    scores = util_gain + gap_penalty
    return scores
