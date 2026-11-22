def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    # Penalize residual capacities that are close to exact multiples of item size (fragmentation risk)
    frag_penalty = np.sin(np.pi * residual / (item + 1e-9)) ** 2
    # Reward bins where item fills the space evenly (residual near multiples of item)
    fill_reward = np.cos(np.pi * residual / (item + 1e-9)) ** 2
    scores = fill_reward / (residual + 1e-9) - frag_penalty * (residual / (item + 1e-9))
    return scores
