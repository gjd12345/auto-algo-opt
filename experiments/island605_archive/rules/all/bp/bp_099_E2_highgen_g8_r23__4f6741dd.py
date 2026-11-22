def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    mod_residual = residual % item
    # Prefer bins where residual is a multiple of item (mod_residual == 0), giving high base score;
    # among those, prefer smaller residual to keep bins full.
    # For others, score decreases with larger mod_residual, and tie-break by residual size.
    scores = np.where(mod_residual == 0, 1000 - residual, -mod_residual * 100 - residual)
    return scores
