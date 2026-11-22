def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    util_gain = np.log(1 + item / (bins + 1e-9))
    penalty = np.where(residual < item, (residual ** 3) / (bins + 1e-9), 0.0)
    reward = np.where(residual % item == 0, 1.0 / (1 + np.exp(-residual / (item + 1e-9))), 0.0)
    scores = util_gain - penalty + reward
    return scores
