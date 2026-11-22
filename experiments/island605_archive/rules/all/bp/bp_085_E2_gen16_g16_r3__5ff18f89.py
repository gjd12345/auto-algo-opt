def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Quadratic tight-fit bonus: stronger reward for nearly full bins
    tightness = (item / bins) ** 2
    # Harmonic penalty: penalize residuals that are small relative to capacity, using harmonic-like decay
    harmonic_penalty = np.where(residual > 0, 1.0 / (residual / bins + 1e-9), 0.0)
    # Cosine capacity pressure: prefer bins with residual near golden ratio fraction (≈0.618)
    capacity_pressure = (1.0 + np.cos(2.0 * np.pi * (residual / bins - 0.618))) / 2.0
    scores = 2.0 * tightness + 0.3 * harmonic_penalty + 2.5 * capacity_pressure
    return np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)
