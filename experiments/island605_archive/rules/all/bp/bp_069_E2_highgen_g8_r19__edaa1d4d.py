def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    harmonic_entangle = np.where(item == bins, 1.0, (item * np.log(bins / item)) / (bins - item + 1e-9))
    hyper_decay = 1.0 / (np.cosh(residual) + 1e-9)
    occupancy_osc = np.abs(np.sin(np.pi * (bins / item) % 1.0))
    scores = harmonic_entangle * hyper_decay + 0.5 * occupancy_osc
    return scores
