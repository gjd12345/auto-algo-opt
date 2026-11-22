def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = item / bins
    cap = bins[0]
    # Penalize residual near 0.25*cap and 0.75*cap
    penalty1 = np.exp(-((residual - 0.25 * cap) ** 2) / (cap * 0.5))
    penalty2 = np.exp(-((residual - 0.75 * cap) ** 2) / (cap * 0.5))
    penalty = 0.4 * penalty1 + 0.4 * penalty2
    scores = utilization - penalty
    return scores
