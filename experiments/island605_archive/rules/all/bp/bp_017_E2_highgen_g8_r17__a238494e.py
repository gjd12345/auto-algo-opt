def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    scores = residual * (residual ^ item)
    # Penalize residuals that are powers of two (often lead to fragmentation)
    is_power_of_two = (residual & (residual - 1)) == 0
    scores = scores - 1e6 * is_power_of_two
    # Ensure exact fit gets highest score
    scores[residual == 0] = np.max(scores) + 1
    return scores
