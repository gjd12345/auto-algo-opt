def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining_after = bins - item
    # Avoid division by zero for full bins after placement
    scores = np.where(remaining_after > 0, item / remaining_after, np.inf)
    # Add small penalty proportional to bin index for deterministic tie-breaking
    scores -= np.arange(len(bins)) * 1e-10
    return scores
