def score(item: int, bins: np.ndarray) -> np.ndarray:
    new_res = bins - item
    # Utility: item divided by bin capacity, scaled softly with sqrt
    utility = (item / (bins + 1e-9)) ** 0.5
    # Exponential penalty for small residuals (below item * 0.6) to avoid fragmentation
    penalty = np.where(new_res < item * 0.6, 0.5, 0.0)
    # Bonus for reaching utilization above 85% after assignment
    bonus = np.where((new_res == 0) | (new_res / (bins + 1e-9) < 0.15), 40.0, 0.0)
    return utility - penalty + bonus
