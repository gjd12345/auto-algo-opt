def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Penalize residuals that are not multiples of the item (to encourage tight fits or future divisibility)
    mod_penalty = residual % item
    # Prefer bins where residual is either 0 (perfect fit) or large enough to be useful (above item threshold)
    utility = np.where(residual == 0, 10.0, np.where(residual >= item, residual / (residual + 1), residual / (item + 1)))
    # Subtract normalized mod penalty to break ties
    return utility - mod_penalty / (item + 1)
