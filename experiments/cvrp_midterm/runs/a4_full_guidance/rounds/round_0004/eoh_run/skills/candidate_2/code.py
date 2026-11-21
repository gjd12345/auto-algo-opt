def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = float(distance_matrix[current_node][depot])

    # Clarke-Wright style savings: reward inserting j between depot and current.
    score = d_cd + d_dep - d_cur

    s_min = float(np.min(score))
    s_max = float(np.max(score))
    span = s_max - s_min
    tol = 0.15 * span
    near = score >= (s_max - tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    cand_demands = demands[candidates]
    cand_cur = distance_matrix[current_node][candidates]
    cand_dep = distance_matrix[depot][candidates]

    # Secondary: demand served per unit of added detour (scale-invariant).
    detour = cand_cur + cand_dep - float(distance_matrix[current_node][depot])
    eps = 1e-9
    secondary = cand_demands / (detour + eps)
    best_idx = int(np.argmax(secondary))
    return int(candidates[best_idx])