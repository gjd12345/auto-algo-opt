def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    residual = bins - item
    item_ratio = item / (bins + 1e-9)
    harmonic = 2.0 / (1.0 / (item_ratio + 1e-9) + 1.0 / (np.exp(-residual) + 1e-9))
    cubic_root = np.cbrt(harmonic + 1e-9)
    fullness = (bins.max() - residual) / (bins.max() + 1e-9)
    circular_weight = np.exp(3.0 * np.cos(2.0 * np.pi * fullness))
    scores = cubic_root * circular_weight
    return scores
