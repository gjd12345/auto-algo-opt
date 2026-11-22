def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    # Dynamic target: average of remaining bin capacities
    avg_capacity = np.mean(bins)
    # Base score: proportion of bin used by item (higher = more urgent fill)
    base_scores = item / bins
    # Penalty: absolute deviation from average capacity, normalized
    penalties = np.abs(bins - avg_capacity) / (avg_capacity + 1e-9)
    # Combine: prefer high fill ratio with low capacity deviation
    scores = base_scores - 0.5 * penalties
    # Tie-break by index (earlier bin preferred on equal score)
    scores = scores - np.arange(len(scores)) * 1e-9
    return scores
