def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins.max() + item  # approximate original capacity
    after = bins - item
    ratios = after / capacity
    scores = ratios * np.log(ratios + 1e-9)  # entropy-like penalty for empty bins
    scores += np.linspace(0, 1e-6, len(bins))[::-1]  # tie-break by smallest index
    return scores
