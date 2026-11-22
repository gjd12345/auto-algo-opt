def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Logarithmic utilization reward: increases with tighter fit but saturates slowly
    log_reward = np.log1p(residual / (item + 1e-9))
    # Squared sine penalty for residuals that are modulo–pattern misaligned (e.g., near 1, 2, etc.)
    sin_penalty = np.sin(residual * np.pi / (item + 1e-9)) ** 2
    # Linear decay term: prefer smaller residuals (tighter fit)
    linear_decay = residual / (bins + 1e-9)
    scores = -log_reward - sin_penalty * 0.5 - linear_decay * 0.3
    return scores.astype(np.float64)
