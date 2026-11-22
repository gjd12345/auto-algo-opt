def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    ratio = item / bins
    penalty = np.log(1 + residual / bins)
    bonus = np.exp(-ratio)
    return bonus - penalty
