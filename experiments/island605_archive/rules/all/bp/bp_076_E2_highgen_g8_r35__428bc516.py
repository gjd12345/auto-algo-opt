def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    efficiency = (item / bins) ** 2
    gap_penalty = np.exp(-5 * (residual / bins) ** 2) * np.sin(2 * np.pi * residual / bins) ** 2
    logistic_boost = 1 / (1 + np.exp(-10 * (residual - 0.5 * item) / bins))
    scores = efficiency - 0.3 * gap_penalty + 0.2 * logistic_boost
    return np.nan_to_num(scores, nan=-1e9, posinf=1e9, neginf=-1e9)
