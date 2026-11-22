def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    import numpy as np

    rem = bins - item
    capacity = 100.0
    util = (capacity - rem) / capacity

    # Cubic utilization gain
    util_gain = util ** 3

    # Cosine-modulated penalty on residual waste: sharp near small gaps, smooth elsewhere
    waste_penalty = np.cos(2.0 * np.pi * rem / capacity) * np.exp(-3.0 * rem / capacity)

    # Sigmoid asymmetry term favoring fuller bins
    fullness_asym = 1.0 / (1.0 + np.exp(-10.0 * (util - 0.5)))

    scores = util_gain + 0.2 * fullness_asym + 1.5 * waste_penalty

    return scores
