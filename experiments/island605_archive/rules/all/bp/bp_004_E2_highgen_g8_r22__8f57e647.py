def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_res = bins.max()
    # Logistic potential: high reward for bins that will be nearly full
    logistic_reward = 1 / (1 + np.exp(-5 * (residual / max_res - 0.15)))
    # Harmonic decay reward: inversely proportional to residual, but flattened for mid-range
    harmonic_reward = 1 / (np.log(residual + 1) + 1e-6)
    # Sigmoid weight blending: favor logistic for small residuals, harmonic for medium
    blend_weight = 1 / (1 + np.exp(3 * (residual / max_res - 0.4)))
    scores = blend_weight * logistic_reward + (1 - blend_weight) * harmonic_reward
    # Absolute priority for perfect fit
    scores[residual == 0] = 1e9
    return scores
