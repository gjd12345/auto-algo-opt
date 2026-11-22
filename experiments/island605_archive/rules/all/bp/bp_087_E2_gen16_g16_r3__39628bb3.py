def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    gap_ratio = residual / bins.max()
    # Hyperbolic tangent of gap ratio for smooth scaling
    tanh_term = np.tanh(2.0 * (1.0 - gap_ratio))
    # Sinusoidal modulation penalizing gaps near 0.3 and 0.7 fractions
    sin_penalty = np.sin(3.0 * np.pi * gap_ratio) ** 2
    # Gaussian decay for moderately filled bins (peak at 0.4 gap fraction)
    gauss_decay = np.exp(-10.0 * (gap_ratio - 0.4) ** 2)
    scores = tanh_term - 0.2 * sin_penalty + 0.1 * gauss_decay
    return scores
