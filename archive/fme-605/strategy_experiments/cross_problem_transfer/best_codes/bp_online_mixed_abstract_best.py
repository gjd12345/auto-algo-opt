# 正式证据来源: cross_problem_transfer/bp_online/mixed_abstract/3101
# Core/primary held-out score: 0.867
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    half_cap = bins.max() / 2  # approximate half capacity from largest bin
    power = 1.5
    # Score: larger inverse residual encourages small leftover; penalty for deviation from half capacity
    scores = (1.0 / (residual ** power)) - (abs(residual - half_cap) / half_cap)
    return scores
