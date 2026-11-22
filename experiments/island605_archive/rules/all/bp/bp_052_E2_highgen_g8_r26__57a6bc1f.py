def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # fractal spacing index: ratio of item to bin capacity, scaled logarithmically
    frac = np.log1p(item / (bins + 1e-9))
    # geometric median of residuals (robust central tendency)
    med = np.median(residual)
    # harmonic alignment: deviation from median weighted by fractal index
    alignment = 1.0 / (1.0 + np.abs(residual - med) / (item + 1e-9))
    harmonic_score = frac * alignment
    # logistic penalty for residuals not near integer multiples of item size
    near_multiple = np.exp(-((residual % (item + 1e-9)) ** 2) / (2.0 * (item * 0.1 + 1e-9)))
    penalty = 2.0 / (1.0 + np.exp(-5.0 * (near_multiple - 0.5)))
    scores = harmonic_score + 0.25 * penalty
    return np.where(np.isfinite(scores), scores, -1e9)
