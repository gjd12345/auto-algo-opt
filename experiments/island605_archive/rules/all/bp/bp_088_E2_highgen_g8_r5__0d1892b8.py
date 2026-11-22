def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    # Sinusoidal penalty: low when residual is near multiples of item size (even filling), high otherwise
    penalty = 1.0 + 0.5 * np.sin(2 * np.pi * residual / (item + 1e-8))
    # Use reciprocal to make small penalty give high score
    scores = utilization / (penalty + 0.1) / bins
    return scores
