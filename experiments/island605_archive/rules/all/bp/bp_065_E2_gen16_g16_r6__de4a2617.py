def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    normalized_residual = residual / (item + 1e-9)
    # Logistic reward for small residuals (tight fit)
    logistic_reward = 1.0 / (1.0 + np.exp(normalized_residual * 5.0))
    # Sinusoidal penalty for residuals that are multiples of the item
    wave_penalty = np.abs(np.sin(2.0 * np.pi * residual / (item + 1e-9)))
    scores = logistic_reward - wave_penalty
    return scores
