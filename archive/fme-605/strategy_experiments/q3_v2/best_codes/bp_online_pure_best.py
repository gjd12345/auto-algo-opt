# 正式证据来源: bp_ablation_cards_q3/bp_online/pure/2028
# Core/primary held-out score: 1.665
def score(item: int, bins: np.ndarray) -> np.ndarray:
    remaining_after = bins - item
    exact_match_bonus = np.where(remaining_after == 0, 1e3, 0)
    capacity_penalty = np.where(remaining_after < 0, 1e6, 0)
    distance_reward = 1 / (1 + np.abs(remaining_after - item))
    return distance_reward + exact_match_bonus - capacity_penalty
