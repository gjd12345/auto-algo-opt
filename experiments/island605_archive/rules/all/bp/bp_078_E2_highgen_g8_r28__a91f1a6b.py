def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Compute a fragmentation metric: penalize residuals that are multiples of item/2
    half_item = item / 2.0
    fragmentation_penalty = np.abs(np.sin(np.pi * residual / (item + 1e-9))) ** 2
    # Compute second-difference-like curvature of packing potential
    # Use log of residual+1 to amplify small residual differences
    curvature = np.log(residual + 1.0) * fragmentation_penalty
    # Inverse residual with fragmentation-aware scaling
    scores = 1.0 / (residual + 1e-9) + curvature
    tie_break = -np.arange(len(bins)) * 1e-12
    return scores + tie_break
