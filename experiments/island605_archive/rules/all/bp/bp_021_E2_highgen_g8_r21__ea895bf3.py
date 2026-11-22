def score(item: int, bins: np.ndarray) -> np.ndarray:
    phi = (1 + np.sqrt(5)) / 2
    residual = bins - item
    fib_depth = np.abs(residual - bins / phi) / (bins + 1e-8)
    fib_score = np.exp(-fib_depth)
    perfect_power = np.round(residual ** (1/3)) ** 3
    power_penalty = 0.4 * (np.abs(residual - perfect_power) < 1e-6).astype(float)
    tight_bonus = 1.0 / (residual + 1e-8)
    scores = fib_score + tight_bonus - power_penalty
    return np.where(np.isfinite(scores), scores, 0.0)
