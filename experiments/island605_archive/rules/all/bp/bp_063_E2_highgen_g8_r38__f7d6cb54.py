def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    norm_res = residual / bins.max()
    harmonic = 2 * (norm_res * (1 - norm_res)) / (norm_res + (1 - norm_res) + 1e-9)
    poly_penalty = np.abs((norm_res - 0.618) ** 3) * 5
    exact_match = np.log1p((residual == 0).astype(float) * 100)
    return harmonic - poly_penalty + exact_match
