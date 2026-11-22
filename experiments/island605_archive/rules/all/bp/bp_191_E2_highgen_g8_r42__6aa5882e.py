def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Exponential reward for near-full bins, but avoid exactly zero residual unless perfect fit is rare.
    # Use: score = exp(-abs(residual)) + small decay by index for tie-breaking.
    # However, to strongly prefer bins that become full (residual near 0), we can use 1 / (1 + residual).
    # To avoid division issues when residual=0, we add epsilon.
    eps = 1e-9
    raw = 1.0 / (1.0 + residual + eps)
    # Add tiny index-based penalty to break ties consistently (earlier bin higher).
    indices = np.arange(len(bins), dtype=float)
    return raw - 1e-6 * indices
