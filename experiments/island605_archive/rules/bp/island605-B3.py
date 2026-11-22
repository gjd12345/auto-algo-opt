def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Quadratic waste penalty: strongly prefer smaller residuals
    waste_penalty = 1.0 / (residual * residual + 1e-9)
    # Penalize residuals near half capacity (adjust 50 as needed)
    future_penalty = -np.abs(residual - 50) / 50.0
    # Tie-break: higher index gets slight advantage (reverse of original)
    tie_breaker = np.arange(len(bins)) * 1e-9
    scores = waste_penalty + future_penalty + tie_breaker
    return scores