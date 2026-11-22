def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_ratio = item / bins
    golden = 0.618
    entropy_score = -np.abs(fill_ratio - golden) * np.log(np.abs(fill_ratio - golden) + 1e-9)
    waste_penalty = -np.exp(5 * np.maximum(residual / bins - 0.5, 0))
    return entropy_score + waste_penalty
