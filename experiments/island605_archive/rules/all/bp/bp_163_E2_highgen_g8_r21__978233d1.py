def score(item: int, bins: np.ndarray) -> np.ndarray:
    efficiency = bins - item  # residual capacity after placing item
    # Penalize bins that would end up with very small residual (encourage tight packing)
    penalty = np.where(efficiency < 0.1 * np.max(bins), 1.0, 0.0)
    # Score = negative residual (prefer smaller residual) minus penalty
    scores = -efficiency - penalty
    return scores
