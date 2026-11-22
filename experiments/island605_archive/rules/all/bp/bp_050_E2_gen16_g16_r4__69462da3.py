def score(item: int, bins: np.ndarray) -> np.ndarray:
    residuals = bins - item
    # Binary entropy penalty: treat residual pattern as "runs" - penalize deviation from golden ratio
    golden = (1 + np.sqrt(5)) / 2
    entropy_penalty = np.abs(residuals / (bins + 1e-9) - 1 / golden) * np.log(residuals + 1e-9 + 1)
    # Sigmoidal utilization gain: smooth step preferring high fill
    util_gain = 1 / (1 + np.exp(-10 * (item / (bins + 1e-9) - 0.5)))
    # Fibonacci-modulated geometric decay: reward bins with residual breaking Fibonacci pattern
    fib_seq = np.array([1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    fib_dist = np.min(np.abs(residuals[:, None] - fib_seq), axis=1)
    fib_decay = np.exp(-fib_dist / (item + 1e-9))
    scores = util_gain - entropy_penalty + fib_decay
    return np.nan_to_num(scores, nan=0.0, posinf=1e9, neginf=-1e9)
