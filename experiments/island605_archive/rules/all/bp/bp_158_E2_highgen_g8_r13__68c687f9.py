def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    logistic_util = 1.0 / (1.0 + np.exp(-5.0 * (item / (bins + 1e-9) - 0.5)))
    golden_ratio = (1 + np.sqrt(5)) / 2
    gaussian_penalty = np.where(residual > 0,
                                np.exp(-((residual / (item + 1e-9) - golden_ratio) ** 2) / 0.1),
                                0.0)
    scores = logistic_util * 100 - gaussian_penalty * 30
    return scores
