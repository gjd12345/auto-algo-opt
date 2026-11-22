def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    capacity = 100  # assuming standard capacity, could be passed otherwise
    residual = bins - item
    density = 1 - residual / capacity
    # score = -residual * density, higher density and lower residual give higher score
    scores = -residual * density
    # add tiny decreasing bonus for earlier indices to break ties
    scores += np.linspace(1e-9, 0, len(bins))
    return scores
