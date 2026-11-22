def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    harmonic_penalty = 1.0 / (residual + 1e-9)
    balance_peak = np.exp(-((residual / (bins.mean() + 1e-9) - 0.5) ** 2) * 10)
    scores = harmonic_penalty + balance_peak
    return scores
