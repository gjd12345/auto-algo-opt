# 正式证据来源: cross_problem_transfer/bp_online/local_only/3101
# Core/primary held-out score: 0.768
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    ideal_leftover = bins.max() * 0.4  # target leftover as 40% of max bin capacity
    alpha = 2.0  # exponent for tight-fit penalty
    beta = 1.5   # weight for deviation penalty from ideal leftover
    tight_penalty = 1.0 / (residual ** alpha + 1e-8)
    ideal_deviation = beta * abs(residual - ideal_leftover) / ideal_leftover
    scores = tight_penalty - ideal_deviation
    return scores
