def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    cap = bins.max()
    normalized = residual / cap
    uniform = 1.0 / len(bins)
    entropy = -normalized * np.log(normalized + 1e-10) - (1 - normalized) * np.log(1 - normalized + 1e-10)
    divergence = np.abs(entropy - (uniform * np.log(1/uniform + 1e-10)))
    return 1.0 / (1.0 + divergence)
