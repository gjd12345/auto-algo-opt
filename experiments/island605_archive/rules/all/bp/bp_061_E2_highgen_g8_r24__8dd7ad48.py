def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    compaction_reward = np.exp(1.0 - residual / bins)
    fragmentation_penalty = np.where(residual < item / 2.0, np.log(residual + 1.0) * 0.3, 0.0)
    scores = compaction_reward - fragmentation_penalty
    return np.maximum(scores, 0.0)
