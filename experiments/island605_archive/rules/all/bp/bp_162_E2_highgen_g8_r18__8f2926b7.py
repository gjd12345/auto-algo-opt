def score(item: int, bins: np.ndarray) -> np.ndarray:
    total_cap = np.max(bins) + item  # approximate total bin capacity
    used_after = 1 - (bins - item) / total_cap
    # avoid log(0) by clipping
    used_after = np.clip(used_after, 1e-10, 1.0)
    log_util = np.log(used_after)
    # bin index penalty: earlier bins get higher score
    idx_penalty = np.exp(-np.arange(len(bins)) * 0.1)
    scores = log_util * idx_penalty
    return scores
