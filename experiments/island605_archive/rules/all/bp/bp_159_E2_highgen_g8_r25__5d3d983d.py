def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    harmonic_scores = 1.0 / (residual + 1.0)
    new_bin_penalty = 1.0 / (np.arange(len(bins)) + 1.0)
    modulation = np.sin(0.5 * np.arange(len(bins))) + 1.5
    scores = harmonic_scores * new_bin_penalty * modulation
    return scores
