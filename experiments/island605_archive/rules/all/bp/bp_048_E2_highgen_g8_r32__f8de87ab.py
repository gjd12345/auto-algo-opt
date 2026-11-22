def score(item: int, bins: np.ndarray) -> np.ndarray:
    import numpy as np

    residual = bins - item
    # Fragmentation penalty: penalize residual between 20% and 50% of item size
    low = max(1, int(0.2 * item))
    high = max(low + 1, int(0.5 * item))
    penalty = np.where((residual >= low) & (residual <= high), 1.5, 0.0)
    # Exact fill bonus: scale by item size
    perfect_bonus = np.where(residual == 0, 8.0, 0.0)
    # Base score: inverse of residual, favoring fuller bins
    base_score = 1.0 / (residual + 1e-6)
    # Combine
    scores = base_score - penalty + perfect_bonus
    # Deterministic tie-break by bin index (earlier bins get slight edge)
    indices = np.arange(len(bins), dtype=np.float64)
    scores += 1.0 / (indices + 1.0) * 1e-6
    return scores
