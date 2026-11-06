# 正式证据来源: bp_card_component_q3/bp_online/residual_poly_only/2025
# Core/primary held-out score: 4.077
def score(item: int, bins: np.ndarray) -> np.ndarray:
    # Avoid division by zero; capacity is known from context, assume 1.0 for normalization
    cap = 1.0
    remaining = bins
    gap = remaining - item
    # Penalize gaps that are too small to be useful (e.g., < 0.1 * cap) or in a low-utility band
    penalty = np.where(
        (gap > 0) & (gap < 0.15 * cap) | ((gap > 0.3 * cap) & (gap < 0.45 * cap)),
        0.1,
        0.0
    )
    # Reward tighter fits, with curvature to prefer filling bins
    fit_reward = (item / remaining) ** 0.5
    return fit_reward - penalty
