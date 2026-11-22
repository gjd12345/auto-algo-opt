def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining_after = bins - item
    fibs = np.array([1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233])
    # Find nearest Fibonacci number <= remaining_after for each bin
    nearest_fib = np.zeros_like(remaining_after)
    for f in fibs:
        mask = remaining_after >= f
        nearest_fib[mask] = f
    dist = np.abs(remaining_after - nearest_fib)
    scores = -dist - 1e-9 * remaining_after
    return scores
