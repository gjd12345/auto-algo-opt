def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    perfect_fit = np.where(residual == 0, 10.0, 0.0)
    balance_penalty = np.exp(-np.abs(item - bins / 2.0) / (bins + 1e-9))
    scores = perfect_fit + balance_penalty
    return scores
