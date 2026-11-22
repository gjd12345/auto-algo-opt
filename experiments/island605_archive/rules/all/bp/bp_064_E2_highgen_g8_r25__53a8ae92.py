def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins[0] + item
    remaining = bins - item
    k_vals = np.array([1, 2, 3, 4, 5])
    target_residuals = capacity * (1 - 1 / np.exp(k_vals))
    harmonic_fit = -np.min(
        np.abs(remaining[:, None] - target_residuals[None, :]),
        axis=1
    ) / capacity
    small_gap_penalty = np.where(
        (remaining > 0) & (remaining < 1.5 * item),
        -1e5,
        0.0
    )
    util_penalty = -remaining / capacity
    raw_score = util_penalty + harmonic_fit + small_gap_penalty
    max_abs = np.max(np.abs(raw_score)) + 1e-12
    scores = raw_score / max_abs
    return scores
