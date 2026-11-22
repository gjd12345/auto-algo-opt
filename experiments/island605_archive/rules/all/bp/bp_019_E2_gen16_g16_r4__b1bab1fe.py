def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    residual = bins - item
    # Gaussian-style utilization peak near full capacity
    util_peak = np.exp(-((bins - item) ** 2) / (2 * (item * 0.1) ** 2 + 1e-8))
    # Exponential penalty for small residuals that are hard to use
    small_gap_penalty = np.where(
        (residual > 0) & (residual < item),
        np.exp(-residual / (item * 0.3 + 1e-8)),
        0
    )
    # Logarithmic tie-breaking: prefer earlier bins slightly
    tie_break = 1e-6 * np.log(1 + np.arange(1, len(bins) + 1))
    return util_peak - small_gap_penalty + tie_break
