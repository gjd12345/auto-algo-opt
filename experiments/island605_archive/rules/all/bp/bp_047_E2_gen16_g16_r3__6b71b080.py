def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max() + item
    residual = bins - item
    normalized_residual = residual / capacity
    # Quadratic penalty for small residual (high penalty when residual is tiny)
    penalty = (1 - normalized_residual) ** 2
    # Linear age bonus (older bins have higher index, get larger bonus)
    age_bonus = 0.1 * np.arange(len(bins))
    # Bonus for exact fit (residual almost zero)
    exact_fit_bonus = 1.0 * (residual < 1e-6).astype(float)
    scores = -penalty + age_bonus + exact_fit_bonus
    return scores
