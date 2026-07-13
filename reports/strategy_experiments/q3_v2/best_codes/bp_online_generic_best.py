# 正式证据来源: bp_ablation_cards_q3/bp_online/generic/2026
# Core/primary held-out score: 2.173
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    target_multiple = 50
    fragmentation_threshold = 20
    # Primary reward: inverse of residual (smaller is better), capped
    primary = np.where(residual == 0, 1e9, 1.0 / (residual + 1e-9))
    # Alignment bonus: strongly reward residual exactly equal to target_multiple
    alignment_bonus = np.where(residual == target_multiple, 10.0, 1.0)
    # Fragmentation penalty: penalize if residual < fragmentation_threshold (but still feasible)
    fragmentation_penalty = np.where(residual < fragmentation_threshold, 0.1, 1.0)
    # Exact fit reward
    exact_fit_reward = np.where(residual == 0, 5.0, 1.0)
    scores = primary * alignment_bonus * fragmentation_penalty * exact_fit_reward
    # Deterministic tie-breaking by reverse index (prefer later bins)
    scores += 1e-10 * np.arange(len(bins) - 1, -1, -1)
    return scores
