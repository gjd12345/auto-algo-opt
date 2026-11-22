def score(item: int, bins: np.ndarray) -> np.ndarray:
    residuals = bins - item
    used_ratio = item / bins
    entropy_penalty = used_ratio * np.log(used_ratio + 1e-10) + (1 - used_ratio) * np.log(1 - used_ratio + 1e-10)
    scores = 1.0 / (residuals + 0.1) - entropy_penalty * 0.5
    return scores
