def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    max_cap = bins.max()
    fill_ratio = residual / max_cap
    tanh_reward = np.tanh(5 * (1 - fill_ratio - 0.5)) + 1
    log_penalty = np.where(
        residual == 0,
        2.0,
        np.where(
            (residual > 0) & (residual < 0.2 * max_cap),
            -np.log1p(residual / max_cap * 10),
            0.0
        )
    )
    exact_bonus = np.where(residual % item == 0, 0.5, 0.0)
    scores = tanh_reward * (1 + log_penalty + exact_bonus)
    return scores
