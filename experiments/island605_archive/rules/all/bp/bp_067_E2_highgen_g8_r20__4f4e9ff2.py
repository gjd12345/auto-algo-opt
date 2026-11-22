def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    capacity = bins + item
    item_ratio = item / capacity
    # compute entropy-like measure: for each bin, how evenly residual distributes across item-sized blocks
    num_blocks = residual // item
    remainder = residual - num_blocks * item
    uniformity_penalty = remainder * np.log(remainder + 1e-12) / (item + 1)
    scores = -item_ratio * uniformity_penalty
    return scores
