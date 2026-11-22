def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np
    residual = bins - item
    fit_efficiency = (item / bins.astype(float)) ** 3
    norm_residual = residual / (bins + 1e-9)
    cap_ratio = bins / (bins.max() if bins.max() > 0 else 1.0)
    sigmoid_penalty = 1 / (1 + np.exp(-10 * (cap_ratio - 0.7)))
    score_val = fit_efficiency * (1 + 0.2 * norm_residual) + 0.1 * sigmoid_penalty
    return score_val
