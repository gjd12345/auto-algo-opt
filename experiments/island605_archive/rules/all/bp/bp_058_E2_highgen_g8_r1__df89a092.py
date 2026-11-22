def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    import numpy as np
    residual = bins - item
    # Reciprocal reward for small residual, plus sinusoidal deviation penalty from 0.75 fullness target
    fullness = (bins - residual) / bins
    target = 0.75
    scores = 1.0 / (residual + 0.01) - np.sin(5 * np.pi * (fullness - target))
    return scores
