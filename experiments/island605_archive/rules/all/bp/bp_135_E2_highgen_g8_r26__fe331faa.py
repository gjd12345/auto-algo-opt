def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    perfect = (residual == 0).astype(float) * 1e9
    fibs = np.array([1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987])
    fib_penalty = np.min(np.abs(residual[:, None] - fibs), axis=1)
    fib_score = np.exp(-0.5 * np.log(1 + fib_penalty))
    util_score = np.exp(-0.05 * residual * residual)
    gap_sigmoid = 1 / (1 + np.exp(3 - residual))
    gap_penalty = np.where((residual > 0) & (residual <= 5), gap_sigmoid, 0)
    scores = perfect + util_score * 0.7 + fib_score * 0.2 - gap_penalty * 0.3
    return scores
