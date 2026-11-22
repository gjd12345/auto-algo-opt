def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    sigmoid_weight = 1 / (1 + np.exp(-5 * (utilization - 0.5)))
    poly_reward = np.power(residual / bins, 1.5)
    n = len(bins)
    kernel = np.cos(np.pi * np.arange(1, n + 1) / (n + 1))
    harmonic_penalty = np.dot(residual, kernel) / (np.linalg.norm(residual) + 1e-9) * kernel
    prime_penalty = np.log2(np.maximum(residual, 1)).astype(int)
    prime_penalty = np.array([bin(x).count('1') for x in prime_penalty], dtype=np.float64) / 10.0
    scores = sigmoid_weight * poly_reward * 2.0 - harmonic_penalty * 0.8 - prime_penalty * 1.5
    scores = np.where(residual == 0, scores + 100.0, scores)
    return np.nan_to_num(scores, nan=-1e9, posinf=1e9, neginf=-1e9).astype(np.float64)
