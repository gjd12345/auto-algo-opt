def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    waste_penalty = -residual * item
    fit_bonus = (residual % item == 0).astype(float) * 1e5
    early_bonus = np.exp(-np.arange(len(bins), dtype=float)) * 100
    return waste_penalty + fit_bonus + early_bonus
