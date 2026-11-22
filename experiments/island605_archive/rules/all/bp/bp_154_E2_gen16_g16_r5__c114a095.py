def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    capacity = bins.max() + item
    if capacity <= 0 or len(bins) == 0:
        return np.zeros_like(bins, dtype=float)

    # Logarithmically spaced targets from 0.1*capacity to 0.9*capacity
    num_targets = 5
    targets = np.geomspace(0.1 * capacity, 0.9 * capacity, num=num_targets)

    # Score based on inverse of squared deviation from nearest target
    scores = np.zeros_like(residual, dtype=float)
    for target in targets:
        diff = np.abs(residual - target)
        scores += 1.0 / (1.0 + diff * diff)

    # Bonus for very small residuals (near full bin)
    scores += 3.0 / (1.0 + residual)

    # Penalty for residuals that are too large (wasteful)
    scores -= 2.0 * (residual > 0.7 * capacity)

    # Tie-break: slight bonus for earlier bins (lower index)
    scores += np.linspace(0, 0.01, num=len(bins))[::-1]

    return scores
