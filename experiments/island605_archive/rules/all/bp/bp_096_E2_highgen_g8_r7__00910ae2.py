import numpy as np

def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    residual = bins - item
    fullness = 1 - residual / bins
    # Ideal residual: exactly divisible by item (residual % item == 0)
    ideal_residual_ratio = 1 / (1 + np.abs(residual % item))
    # Euclidean distance from ideal point (fullness=1, ideal_residual_ratio=1)
    dist = np.sqrt((1 - fullness)**2 + (1 - ideal_residual_ratio)**2)
    scores = 1 / (dist + 1e-9)
    return scores
