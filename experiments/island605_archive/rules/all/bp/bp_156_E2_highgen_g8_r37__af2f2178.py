def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = bins + (bins.max() - bins.min() + item)  # approximate total capacity (same for all)
    # more robust: infer capacity as max residual + item across all bins
    cap = bins.max() + item
    usage = (cap - bins + item) / cap
    scores = usage ** 2 * (1 - (bins < cap / 2).astype(float) * 0.5)
    return scores
