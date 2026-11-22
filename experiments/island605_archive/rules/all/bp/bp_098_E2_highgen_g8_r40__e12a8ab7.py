def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    norm_residual = residual / (bins.max() + 1e-10)
    logistic_penalty = 1.0 / (1.0 + np.exp(5.0 * (norm_residual - 0.5)))
    match_bonus = 1.0 / (1.0 + (residual - item)**2)
    scores = logistic_penalty + 0.5 * match_bonus
    scores = np.where(residual == 0, np.inf, scores)
    return scores
