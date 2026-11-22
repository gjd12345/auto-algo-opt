def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining = bins - item
    decay_rate = 0.1
    waste_penalty_threshold = 3.0
    waste_penalty = -1e9
    # Reward bins that leave small residual, with exponential decay for larger residuals
    scores = np.exp(-decay_rate * remaining)
    # Strongly penalize bins that would leave too much wasted capacity
    scores[remaining > waste_penalty_threshold] = waste_penalty
    return scores
