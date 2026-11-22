def score(item: int, bins: np.ndarray) -> np.ndarray:
    residuals = bins - item
    floor_mult = (residuals // item) * item
    ceil_mult = floor_mult + item
    gap_to_floor = residuals - floor_mult
    gap_to_ceil = ceil_mult - residuals
    min_gap = np.minimum(gap_to_floor, gap_to_ceil)
    weight = 1.0 / (residuals + 1)
    scores = -weight * (min_gap ** 2)
    return scores
