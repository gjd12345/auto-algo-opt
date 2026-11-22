def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    used = item
    waste = bins - item
    ratio = np.where(waste > 0, (waste + 1) / (used + 1), 1e9)
    scores = ratio - np.arange(len(bins)) * 0.1
    return scores
