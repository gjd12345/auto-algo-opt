def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Primary score: return-savings ratio (scale-invariant), same functional
    # form as the parent but with a span-proportional near-tie gate.
    eps = 1e-9
    score = d_dep / (d_cur + eps)

    # Span-proportional near-tie window: relative to the range of the score,
    # not to the absolute maximum, so the gate is invariant to coordinate scale.
    s_min = np.min(score)
    s_max = np.max(score)
    span = s_max - s_min
    tol = 0.05 * span
    near = score >= (s_max - tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    # Secondary ordering: among near-ties, prefer the candidate whose
    # "return distance" from current node plus depot leg is largest
    # (i.e. strongest detour saving), breaking residual ties by nearest.
    cand_dep = distance_matrix[depot][candidates]
    cand_cur = distance_matrix[current_node][candidates]
    secondary = cand_cur + cand_dep  # maximizes the amount "absorbed" next step
    best_idx = int(np.argmax(secondary))
    return int(candidates[best_idx])