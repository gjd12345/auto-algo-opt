def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Harmonic proximity: reward if residual is near target fractions of capacity (e.g., 0.25, 0.5, 0.75 of max capacity)
    max_cap = np.max(bins + item) if len(bins) > 0 else item
    targets = np.array([0.25, 0.5, 0.75]) * max_cap
    proximity = np.max(1.0 - np.abs(residual[:, None] - targets[None, :]) / (max_cap + 1e-8), axis=1)
    # Waste penalty: larger residual gaps are penalized, scaled logarithmically
    waste_penalty = np.log1p(residual) / (1.0 + np.log1p(max_cap))
    # Combine: positive proximity reward minus waste penalty, plus base to ensure finite scores
    scores = proximity - waste_penalty * 0.4 + 0.1
    return scores
