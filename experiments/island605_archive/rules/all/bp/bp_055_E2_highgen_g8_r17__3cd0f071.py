def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Sigmoid-based utilization reward: prefer high utilization, but saturate near full
    util_reward = 1.0 / (1.0 + np.exp(-10.0 * (residual / bins.max() - 0.5)))
    # Exponential penalty for residuals that are in "dead zones" (e.g., very small or awkward gaps)
    dead_zone_penalty = np.exp(-10.0 * np.abs(residual - item * np.floor(residual / (item + 1e-8))))
    # Logarithmic reward for residuals that are close to an integer fraction of item size
    fraction = residual / (item + 1e-8)
    frac_reward = np.log1p(1.0 / (1.0 + np.abs(fraction - np.round(fraction))))
    scores = util_reward * dead_zone_penalty + 0.3 * frac_reward
    return scores
