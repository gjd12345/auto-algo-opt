def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Score: higher for smaller residual, but also reward when residual is an exact multiple of item or near zero
    harmony = np.where(residual == 0, 1e9, np.where(residual % item == 0, 1000 / (residual + 1), 0))
    scores = 1.0 / (residual + 1) + harmony
    return scores
