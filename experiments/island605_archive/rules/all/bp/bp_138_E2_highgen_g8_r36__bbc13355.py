def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    harmonic_mean = len(bins) / np.sum(1.0 / bins)
    capacity_ratio = bins / harmonic_mean
    sorted_indices = np.argsort(bins)
    position_penalty = np.arange(len(bins))[np.argsort(sorted_indices)]
    scores = capacity_ratio - 0.05 * position_penalty
    return scores
