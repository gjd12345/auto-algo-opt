def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Cubic root of residual to soften large residual dominance
    cubic_penalty = -np.cbrt(residual)
    # Bonus for residual being close to a multiple of item (reducing fragmentation)
    remainder_mod = residual % item
    bonus = np.where(remainder_mod == 0, 0.5 * item, 0)
    return cubic_penalty + bonus
