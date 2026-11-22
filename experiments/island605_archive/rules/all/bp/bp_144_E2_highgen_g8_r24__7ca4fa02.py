def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    # Approximate original capacity from the first bin's initial capacity (assuming uniform capacity)
    capacity = bins[0] + item  # since bins are feasible, the first bin must have had at least this capacity
    residual = bins - item
    fullness = 1 - residual / capacity
    # Score: prefer smaller residual, penalize low fullness quadratically, add small index tie-break
    scores = -residual * (fullness ** 2 + 1e-9) + np.arange(len(bins)) * 1e-12
    return scores
