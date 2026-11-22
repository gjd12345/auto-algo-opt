def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max() + item + 1e-9
    residual = bins - item
    # Logarithmic efficiency reward: prefer bins where residual fills a high fraction of original capacity
    log_efficiency = np.log1p(item / (bins.astype(float) + 1e-9))
    # Gaussian penalty on bin capacities that are near multiples of 7, 11, 13 (primes to shatter rigid patterns)
    norm_cap = bins / capacity
    penalty = -np.exp(-50 * (norm_cap - 0.14285)**2) - np.exp(-50 * (norm_cap - 0.27272)**2) - np.exp(-50 * (norm_cap - 0.23077)**2)
    # Small bonus for exact fill
    exact_bonus = np.where(residual == 0, 50.0, 0.0)
    scores = log_efficiency + penalty * 0.5 + exact_bonus
    return np.nan_to_num(scores, nan=0.0, posinf=1e9, neginf=-1e9)
