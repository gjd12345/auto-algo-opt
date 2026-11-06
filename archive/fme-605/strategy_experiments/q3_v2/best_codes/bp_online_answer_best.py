# 正式证据来源: bp_ablation_cards_q3/bp_online/answer/2026
# Core/primary held-out score: 1.346
def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = 100
    residuals = bins - item
    exact_fit = (residuals == 0).astype(float) * 1e6
    small_penalty = np.where((residuals > 0) & (residuals < item / 2), 1e4, 0)
    moderate_boost = np.where((residuals >= item) & (residuals <= 2 * item), 2000, 0)
    large_penalty = np.where(residuals > capacity / 2, 1000, 0)
    base = residuals.astype(float)
    scores = base - small_penalty + moderate_boost - large_penalty + exact_fit
    return scores
