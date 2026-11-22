def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util_gain = item / bins
    frag_penalty = np.exp(-0.5 * residual)
    alignment = np.minimum(residual % 5.0, 5.0 - residual % 5.0)
    align_bonus = 0.3 * np.exp(-alignment)
    scores = util_gain * frag_penalty + align_bonus
    tiebreaker = residual / bins
    scores += 1e-7 * tiebreaker
    return scores
