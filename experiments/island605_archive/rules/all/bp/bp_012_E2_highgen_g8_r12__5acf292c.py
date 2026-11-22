def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Quadratic penalty scales with residual, but decays faster for larger residuals
    penalty = (residual / (item + 1)) ** 2
    # Reward exact fits heavily, then favor small residuals with mild penalty
    scores = residual + item * (residual == 0) * 2.0 - penalty * item * 0.5
    return scores
