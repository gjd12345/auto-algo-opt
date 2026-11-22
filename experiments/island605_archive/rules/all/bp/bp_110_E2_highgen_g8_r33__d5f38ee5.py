def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    # Logarithmic penalty: higher residual => lower score, with diminishing returns
    log_penalty = 1.0 / (1.0 + np.log1p(residual))
    # Binary bonus for bins where residual is an exact multiple of item (tight packing hint)
    mod_bonus = (residual % item == 0).astype(float)
    # Combine: prioritize low residual tight fits, with small bonus for exact multiples
    scores = log_penalty + 0.2 * mod_bonus
    return scores
