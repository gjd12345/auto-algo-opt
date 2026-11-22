def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    norm_res = residual / (bins.max() + 1e-12)
    scores = -np.log(norm_res + 1e-12)
    indices = np.arange(len(bins)) + 1
    scores += 1.0 / (indices ** 1.0)
    return scores
