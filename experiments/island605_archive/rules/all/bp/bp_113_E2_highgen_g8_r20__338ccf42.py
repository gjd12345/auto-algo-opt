def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Sigmoid utilization: steep increase for tight fit
    util = 1.0 / (1.0 + np.exp(-2.0 * (1.0 - residual / (item + 1e-8))))
    # Squared exponential penalty for residuals near integer multiples of item
    mod_residual = (residual % item) / (item + 1e-8)
    penalty = np.exp(-10.0 * (mod_residual - 0.5)**2)
    # Combine: prefer high utilization and avoid mid-gap residuals
    scores = 100.0 * util - 30.0 * penalty
    return scores
