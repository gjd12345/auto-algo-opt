def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    inverse_residual = 1.0 / (residual + 1e-9)
    capacity_penalty = np.abs(residual - bins.max() / 2) / bins.max()
    base_score = inverse_residual ** 2 - capacity_penalty * 0.5
    step_bonus = (residual % item == 0).astype(float) * 100
    return base_score + step_bonus
