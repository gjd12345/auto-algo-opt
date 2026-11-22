def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util_reward = (item / bins) ** 2
    # Sinusoidal penalty for gaps near multiples of item (avoid small unusable fragments)
    gap_penalty = np.where(residual > 0, np.sin(np.pi * residual / item) * 0.5, 0)
    # Linear boost for bins where residual is close to item (i.e., just above item)
    boost = np.where(np.abs(residual - item) < 0.2 * item, 0.2, 0.0)
    return util_reward - gap_penalty + boost
