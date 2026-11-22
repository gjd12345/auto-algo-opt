def score(item: int, bins: np.ndarray) -> np.ndarray:
    if len(bins) == 0:
        return np.array([], dtype=float)
    residuals = bins - item
    # Sinusoidal preference for residuals that are multiples of item
    oscillation = np.cos(2 * np.pi * residuals / (item + 1e-10))
    # Exponential penalty for large residuals
    waste_penalty = np.exp(-residuals / (item + 1))
    scores = oscillation + waste_penalty
    return scores
