def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    avg_residual = np.mean(bins)
    threshold = avg_residual * 0.3  # lower threshold ratio
    penalty = np.where(residual < threshold, (residual / threshold) ** 2, 1.0)  # squared penalty
    scores = (item / residual) * penalty
    return scores
