def score(item: int, bins: np.ndarray) -> np.ndarray:
    fullness = item / (bins + item)
    penalty = np.where((bins + item) / (bins.max() + item) > 0.8, 100, 0)
    score_val = fullness ** 2 - penalty
    return score_val + np.arange(len(bins)) * 1e-9
