def score(item: int, bins: np.ndarray) -> np.ndarray:
    residuals = bins - item
    log_fit = -np.abs(np.log((residuals % (item + 1e-6)) / (item + 1e-6) + 1e-6))
    step_penalty = 1.0 / (1.0 + np.exp(20 * (residuals / (item + 1e-6) - 0.3)))
    density_bonus = 1.0 / ((residuals + 1e-6) ** 2)
    scores = log_fit * 0.5 + (1.0 - step_penalty) * 0.3 + density_bonus * 0.2
    return scores
