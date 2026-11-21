def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    cand_demands = demands[unvisited_nodes]
    eps = 1e-9

    # Primary: cheapest detour per unit demand served (scale-invariant ratio).
    score = (d_cur + eps) / (cand_demands + eps)

    s_min = float(np.min(score))
    s_max = float(np.max(score))
    span = s_max - s_min
    tol = 0.15 * span + eps
    near = score <= (s_min + tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    # Secondary: Clarke-Wright saving (scale-invariant ordering by raw saving).
    cand_cur = distance_matrix[current_node][candidates]
    cand_dep = distance_matrix[depot][candidates]
    d_cd = float(distance_matrix[current_node][depot])
    saving = d_cd + cand_dep - cand_cur
    best_idx = int(np.argmax(saving))
    return int(candidates[best_idx])