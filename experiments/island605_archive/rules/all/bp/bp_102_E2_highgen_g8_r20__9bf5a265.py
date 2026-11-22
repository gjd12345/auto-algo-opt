def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    perfect = (residual == 0).astype(float) * 1e9
    modular_penalty = np.where(residual > 0, residual % item, 0) * 0.5
    waste_penalty = np.where(residual > 0, residual / (bins + 1e-9), 0)
    scores = perfect + (1 - waste_penalty - modular_penalty) + np.arange(len(bins))[::-1] * 1e-6
    return scores
