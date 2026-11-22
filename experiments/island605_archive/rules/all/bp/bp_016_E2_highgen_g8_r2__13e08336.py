def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    cap = np.max(bins + item)
    ratio = item / cap

    # Harmonic size class weighting (adjusted bounds and weights)
    if ratio > 0.6:
        class_weight = 2.5
    elif ratio > 0.3:
        class_weight = 1.2
    else:
        class_weight = 0.9

    # Base tight-fit reward with larger denominator for softer preference
    base = class_weight * np.sqrt(item) / (residual + 1)

    # Quadratic penalty on unusable gaps: two intervals (0, item*0.15) and (cap*0.03, cap*0.12)
    penalty = 0.0
    small_gap = (residual > 0) & (residual < item * 0.15)
    penalty += small_gap * 1.8 * (1 - (residual / (item * 0.15)) ** 2)
    unusable_range = (residual > cap * 0.03) & (residual < cap * 0.12)
    penalty += unusable_range * 1.2 * (1 - ((residual - cap * 0.03) / (cap * 0.09)) ** 2)

    # Linear reward for residuals near target fractions (1/2, 1/3, 3/4)
    linear_reward = 0.0
    targets = [cap // 2, cap // 3, (3 * cap) // 4]
    for t in targets:
        if t > 0:
            dist = np.abs(residual - t)
            linear_reward += 0.4 * np.maximum(0, 1 - dist / (cap * 0.1))

    scores = base - penalty + linear_reward
    scores = np.where(np.isfinite(scores), scores, -1e12)
    return scores
