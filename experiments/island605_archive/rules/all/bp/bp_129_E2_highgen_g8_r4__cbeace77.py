def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    base = np.arcsinh(residual + 1e-9)
    penalty = np.maximum(0.0, 1.0 - residual / (bins * 0.33 + 1e-9))
    reward = np.where(residual < bins * 0.1, 1.0 / (residual + 1e-9), 0.0)
    return base * penalty + reward
