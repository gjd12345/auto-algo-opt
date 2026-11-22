def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    fill_squared = ((bins - residual) / bins) ** 2
    waste_penalty = np.where((residual % item == 0), 0, np.exp(residual % item))
    scores = fill_squared - waste_penalty
    return scores
