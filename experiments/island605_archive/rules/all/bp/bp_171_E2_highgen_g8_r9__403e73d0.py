def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    epsilon = 1e-9
    # Hyperbolic tangent of utilization ratio, scaled to [0,1]
    util_tanh = np.tanh(item / (bins + epsilon))
    # Sine-wave modulation of residual penalty: penalize residuals in ranges that cause fragmentation
    sin_penalty = np.abs(np.sin(residual * np.pi / 5)) * 0.5
    # Exponential decay bonus for near-full bins (residual close to 0)
    full_bonus = np.exp(-residual / (bins + epsilon))
    scores = util_tanh * 10 - sin_penalty + full_bonus * 5
    return scores
