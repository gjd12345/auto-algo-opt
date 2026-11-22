def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Primary: high score for residual exactly zero, then decreasing, with a penalty for residuals below capacity*0.2
    primary = np.where(residual == 0, 1e9,
                       np.where(residual < 0.2 * (bins + item), residual * 0.5,
                                residual))
    # Secondary: prefer bins that are fuller (smaller residual) after primary tie
    return primary - residual
