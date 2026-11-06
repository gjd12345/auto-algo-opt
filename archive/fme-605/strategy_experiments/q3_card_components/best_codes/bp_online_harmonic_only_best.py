# 正式证据来源: bp_card_component_q3/bp_online/harmonic_only/2025
# Core/primary held-out score: 2.552
def score(item: int, bins: np.ndarray) -> np.ndarray:
    capacity = 100  # assumed fixed capacity; adjust if different
    ratio = item / capacity
    residual = bins - item
    # Base best-fit: prefer smallest feasible residual
    base = 1.0 / (residual + 1e-9)
    if ratio > 0.5:
        # For large items, strongly prefer exact fit
        scores = base * (residual == 0).astype(float) + 0.01 * base
    elif ratio > 0.25:
        # For medium items, penalize if new residual < item/2 (waste for future)
        penalty = (residual < item / 2).astype(float) * 10.0
        scores = base - penalty
    else:
        # For small items, harmonic-style: prefer mid-range residual to avoid filling too much
        ideal = capacity * 0.5
        scores = base * (1.0 - 0.5 * np.abs(residual - ideal) / ideal)
    # Ensure all scores are finite (avoid inf from zero residual)
    scores = np.nan_to_num(scores, nan=0.0, posinf=1e9, neginf=0.0)
    return scores
