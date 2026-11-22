def score(item: int, bins: np.ndarray) -> np.ndarray:
    if not hasattr(score, "history"):
        score.history = []
    score.history.append(item)
    median = np.median(score.history[-50:]) if score.history else item
    residuals = bins - item
    clusters = np.abs(residuals - median * np.round(residuals / max(median, 1)))
    entropy = -np.where(clusters > 0, clusters * np.log(clusters + 1e-9), 0)
    scores = 1.0 / (1.0 + np.exp(-entropy / (median + 1)))
    return scores
