def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util = item / bins
    geo_mean = np.sqrt(util * (residual / bins))
    forbidden_penalty = np.where((residual > 0) & (residual <= 0.1 * bins), 10.0 / (residual + 1e-8), 0)
    exact_fit_reward = np.where(residual == 0, 100.0, 0)
    return geo_mean - forbidden_penalty + exact_fit_reward
