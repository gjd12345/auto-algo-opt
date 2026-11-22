def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    residual = bins - item
    capacity = bins + item
    # Inverted residual: prefer bins with larger leftover space
    inv_residual = 1 / (residual + 1)
    # Utilization penalty: heavily reduce score for bins that would exceed 70% fill
    fill_ratio = 1 - (residual / capacity)
    utilization_penalty = np.where(fill_ratio > 0.7, 0.2, 1.0)
    # Combine: favor larger residual with penalty on high fill
    scores = inv_residual * utilization_penalty
    return scores
