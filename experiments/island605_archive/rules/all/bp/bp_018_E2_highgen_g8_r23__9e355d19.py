def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    frac = residual / bins.max()
    primary = np.sin(np.pi * ((bins / bins.max()) ** 0.7)) * (1.0 / (residual + 1e-9))
    entropy_penalty = np.abs(np.cos(np.pi * frac * 2)) * np.exp(-frac)
    scores = primary - 0.5 * entropy_penalty
    return np.where(np.isfinite(scores), scores, 1e9 * np.sign(residual))
